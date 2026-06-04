"""
engine.py — GameEngine

The GameEngine owns all game logic and state.
It has no knowledge of how output is displayed — no print(), no input().

PUBLIC INTERFACE
================
engine = GameEngine(start_year=1896, num_seasons=3)
state  = engine.advance()     # move to the next event; returns a state dict
state  = engine.choose(index) # resolve a blocking choice; returns a state dict

Every method returns a state dict with at minimum:
    {
        "type":    str,   # identifies what kind of state this is
        "season":  str,   # e.g. "1896/97"
        "date":    str,   # ISO date string of the current calendar date
    }

The "type" field tells the view what to render. Full schemas for each
type are documented on their respective _state_* methods below.

STATE MACHINE
=============
The game moves through these states in order:

    NEEDS_SETUP
        │  advance() with load=True/False
        ▼
    SEASON_IDLE ◄────────────────────────────────┐
        │  advance()                              │
        ▼                                         │
    MATCHDAY  (results, standings, replays)       │
        │  advance()                              │
        ▼                                         │
    BLOCKING_EVENT  (choices or acknowledgement)  │
        │  choose(index)                          │
        ▼                                         │
    SEASON_IDLE ─── (repeat until season ends) ──┘
        │  advance() when no more events
        ▼
    SEASON_END  (final stats, champion)
        │  advance()
        ▼
    BETWEEN_SEASONS  (development log)
        │  advance()
        ▼
    SEASON_IDLE  (next season starts) ── or ──► GAME_OVER
"""

import os
import random
import datetime

from classes import Team, Player, Competition, Season
from classes.competition import CupCompetition
from name_generator import generate_squad
from data_manager import (
    save_teams_to_file,
    load_teams_from_file,
    save_competition_to_file,
    load_competition_data,
    save_records_to_file,
    load_records_from_file,
)
from data_loader import (
    load_nations,
    teams_in_competition,
    competitions_for_season,
    get_nation,
    TeamConfig,
)
from records import RecordBook
from player_refs import find_player
from game_calendar import GameCalendar, apply_effects, apply_match_morale
from rules import get_max_subs, get_yellow_threshold
from simulation import roll_injury_severity


class GameEngine:

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, start_year: int = 1896, num_seasons: int = 3):
        self.start_year  = start_year
        self.num_seasons = num_seasons

        # Persisted across seasons
        self.teams:       list       = []
        self.record_book: RecordBook = RecordBook()

        # Per-season objects, set in _start_season()
        self.season_year:    str         = ""
        self.current_season: Season      = None
        self.comp:           Competition = None
        self.calendar:       GameCalendar = None

        # Internal bookkeeping
        self._season_index:   int  = 0       # which season we're on (0-based)
        self._last_processed: datetime.date = None
        self._pending_event   = None         # blocking non-match event awaiting choice
        self._season_complete: bool = False  # True once end_season() has been called

    # ── Public interface ──────────────────────────────────────────────────────

    def advance(self, load_save: bool = False) -> dict:
        """
        Move the game forward by one step and return a state dict.

        The meaning of "one step" depends on the current situation:
          - If no teams are loaded yet, initialise and return NEEDS_SETUP
            (unless load_save is True, in which case load from disk first)
          - If a blocking event is pending, return it again — the caller
            must call choose() before advancing further
          - If a matchday is due, simulate it and return MATCHDAY
          - If a non-match blocking event is next, return BLOCKING_EVENT
          - If the season is over, finalise it and return SEASON_END
          - If all seasons are done, return GAME_OVER

        load_save is only consulted on the very first advance() call.
        """

        # ── First call: initialise ────────────────────────────────────────────
        if not self.teams:
            return self._initialise(load_save)

        # ── A blocking event is waiting for a choice ──────────────────────────
        if self._pending_event is not None:
            return self._state_blocking_event(self._pending_event)

        # ── Season is fully complete — move between seasons ───────────────────
        if self._season_complete:
            return self._advance_between_seasons()

        # ── Drive the calendar forward ────────────────────────────────────────
        return self._advance_calendar()

    def choose(self, index: int) -> dict:
        """
        Resolve the current blocking event by selecting option `index` (0-based).

        Returns an error state if there is no pending event or the index is
        out of range. Otherwise applies the chosen effects, clears the pending
        event, and advances to the next state.
        """
        if self._pending_event is None:
            return {"type": "error", "message": "No blocking event is pending."}

        event = self._pending_event
        if not event.choices:
            # Acknowledgement-only event — any input dismisses it
            apply_effects(event.effects, self.teams)
            event.is_read = True
            self._pending_event = None
            return self._advance_calendar()

        if index < 0 or index >= len(event.choices):
            return {
                "type":    "error",
                "message": f"Invalid choice. Pick 0–{len(event.choices) - 1}.",
            }

        chosen = event.choices[index]
        apply_effects(chosen.effects, self.teams)
        event.resolution = chosen.text
        event.is_read    = True
        self._pending_event = None
        return self._advance_calendar()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _initialise(self, load_save: bool) -> dict:
        """Load or generate teams, then start the first season."""
        self.record_book = load_records_from_file()

        if os.path.exists("teams_data.json"):
            self.teams = load_teams_from_file("teams_data.json")
        else:
            self.teams = self._bootstrap_teams()
            save_teams_to_file(self.teams)

        self._start_season(load_save=load_save)
        return self._advance_calendar()

    def _bootstrap_teams(self) -> list:
        """
        First-launch team generation.

        Reads teams.yaml to find which teams exist at the start year,
        then checks data/squads/<season_year>.yaml for pre-written squads.
        Falls back to generate_squad() for any team without a squad file.

        This only runs once — the result is saved to teams_data.json and
        loaded from there on every subsequent launch.
        """
        from name_generator import generate_squad

        season_year = self._season_label(0)
        team_configs = teams_in_competition("prote_kategorias", season_year)

        teams = []
        squad_data = self._load_squad_file(season_year)

        for cfg in team_configs:
            team = Team(cfg.name, cfg.attack, cfg.midfield, cfg.defense)
            team.prestige = cfg.prestige
            team.nation_id = cfg.nation_id
            team.league_nation_id = cfg.league_nation_id
            team.league_nation_id_year = cfg.league_nation_id_year

            if cfg.id in squad_data:
                # Pre-written squad from YAML
                team.squad = self._build_squad_from_yaml(squad_data[cfg.id])
            else:
                # Fall back to procedural generation
                nation = get_nation(cfg.nation_id)
                team.squad = generate_squad(
                    cfg.name,
                    average_ca=cfg.avg_ca,
                    nation=nation.name,
                )

            teams.append(team)

        return teams

    def _load_squad_file(self, season_year: str) -> dict:
        """
        Load data/squads/<season_year>.yaml if it exists.
        Returns a dict keyed by team_id, or empty dict if file not found.

        The season_year "1896/97" maps to the filename "1896_97.yaml".
        """
        import yaml
        filename = season_year.replace("/", "_") + ".yaml"
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data", "squads", filename
        )
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _build_squad_from_yaml(self, players_data: list) -> list:
        """
        Build a list of Player objects from a squad YAML entry.

        Expected shape per player:
            name:              str
            position:          GK | DEF | MID | FWD
            age:               int
            current_ability:   int
            potential_ability: int
            squad_number:      int   (optional)
        """
        squad = []
        for p in players_data:
            player = Player(
                name=p["name"],
                position=p["position"],
                age=p["age"],
                current_ability=p["current_ability"],
                potential_ability=p["potential_ability"],
            )
            if "squad_number" in p:
                player.squad_number = p["squad_number"]
            squad.append(player)
        return squad

    def _start_season(self, load_save: bool = False):
        """Initialise all per-season objects."""
        self.season_year    = self._season_label(self._season_index)
        self._season_complete = False

        self.current_season = Season(self.season_year, self.teams)

        self.comp = Competition(
            "Prote Kategorias",
            self.teams,
            max_subs=get_max_subs(self.season_year),
            season_year=self.season_year,
        )
        self.comp.generate_fixtures()
        self.current_season.add_competition(self.comp)

        self.calendar = GameCalendar(self.season_year)
        self.calendar.schedule_fixtures(self.comp)

        if load_save and os.path.exists("competition_data.json"):
            self.comp, saved_date = load_competition_data(self.comp)
            self.calendar.schedule_fixtures(self.comp)
            self.calendar.current_date = saved_date

        self._last_processed = self.calendar.current_date

    # ── Calendar driving ──────────────────────────────────────────────────────

    def _advance_calendar(self) -> dict:
        """
        Move to the next calendar event and process it.

        Background events are consumed silently (no state returned for them —
        they just mutate world state). The first blocking event encountered
        stops the loop and returns a state dict.
        """
        # If the season is already flagged as complete, don't re-enter the loop
        if self._season_complete:
            return self._advance_between_seasons()

        while self.calendar.current_date <= self.calendar.season_end:
            next_date = self.calendar.get_next_event_date(self.calendar.current_date)

            if next_date is None or next_date > self.calendar.season_end:
                return self._finalise_season()

            # Apply weekly morale/relationship decay
            d = self._last_processed
            while d <= next_date:
                if d.weekday() == 0:
                    self.calendar.apply_weekly_decay(self.teams)
                d += datetime.timedelta(days=1)

            self.calendar.current_date = next_date
            events_today = self.calendar.get_events_for_date(self.calendar.current_date)
            dynamic      = self.calendar.roll_dynamic_events(self.teams)
            all_events   = events_today + dynamic

            # Background events — silent
            for event in [e for e in all_events if not e.blocking]:
                apply_effects(event.effects, self.teams)
                self.calendar.inbox.append(event)

            # Blocking events — process and return to caller
            blocking = [e for e in all_events if e.blocking]
            if blocking:
                match_events = [e for e in blocking if e.category == "match"]
                if match_events:
                    state = self._process_matchday()
                    self._last_processed = self.calendar.current_date
                    self.calendar.current_date += datetime.timedelta(days=1)
                    return state

                # Non-match blocking event — park it and return
                self._pending_event = blocking[0]
                self._last_processed = self.calendar.current_date
                self.calendar.current_date += datetime.timedelta(days=1)
                return self._state_blocking_event(self._pending_event)

            self._last_processed = self.calendar.current_date
            self.calendar.current_date += datetime.timedelta(days=1)

        return self._finalise_season()

    # ── Matchday processing ───────────────────────────────────────────────────

    def _process_matchday(self) -> dict:
        """
        Simulate all matches for today, run post-match logic, and return
        a MATCHDAY state dict.

        This is the largest chunk of logic extracted from main.py.
        Every side-effect (stat updates, morale, injuries, suspensions,
        saves) happens here. The returned dict contains all the data the
        view needs to render results, standings, and notifications.
        """
        today_fixtures = [
            f for f in self.comp.fixtures
            if f.get("date") == self.calendar.current_date
        ]
        if not today_fixtures:
            return self._advance_calendar()

        matchday_num = today_fixtures[0]["matchday"]
        if matchday_num in self.comp.completed_matchdays:
            return self._advance_calendar()

        self.comp.current_matchday = matchday_num

        # Simulate
        if self.comp.type == "cup":
            drawn_fixtures = self.comp.simulate_cup_round()
        else:
            self.comp.simulate_matchday()
            drawn_fixtures = []

        recent = self.comp.results[-len(today_fixtures):]

        # Record-book and morale updates
        for result in recent:
            self.record_book.process_match(
                result,
                self.teams,
                competition_name=self.comp.name,
                season_year=self.season_year,
            )
            home_team = next((t for t in self.teams if t.name == result["home_team"]), None)
            away_team = next((t for t in self.teams if t.name == result["away_team"]), None)
            if home_team and away_team:
                apply_match_morale(home_team, away_team, result["home_goals"], result["away_goals"])

        # Cup: schedule replays for draws
        scheduled_replays = []
        for drawn in drawn_fixtures:
            replay_date = self.calendar.schedule_replay(
                self.comp,
                drawn,
                self.calendar.current_date,
            )
            if replay_date:
                scheduled_replays.append({
                    "home_team": drawn["home_team"].name,
                    "away_team": drawn["away_team"].name,
                    "date":      replay_date.isoformat(),
                })

        # Cup: advance winners for completed replays
        if self.comp.type == "cup":
            for fixture in today_fixtures:
                if fixture.get("is_replay"):
                    replay_result = next(
                        (r for r in recent
                         if r["home_team"] == fixture["home_team"].name
                         and r["away_team"] == fixture["away_team"].name),
                        None,
                    )
                    if replay_result:
                        if replay_result["home_goals"] > replay_result["away_goals"]:
                            winner = fixture["home_team"]
                        elif replay_result["away_goals"] > replay_result["home_goals"]:
                            winner = fixture["away_team"]
                        else:
                            winner = None
                        if winner:
                            self.comp.advance_cup_winner(
                                fixture["home_team"],
                                fixture["away_team"],
                                winner,
                            )

        # Yellow card accumulation → suspensions
        yellow_threshold = get_yellow_threshold(self.season_year)
        newly_suspended  = []
        for team in self.teams:
            for player in team.squad:
                if (player.yellow_cards > 0
                        and player.yellow_cards % yellow_threshold == 0
                        and not player.is_suspended):
                    player.is_suspended = True
                    player.suspension_matches_left = 1
                    player.yellow_cards -= yellow_threshold
                    newly_suspended.append({"player": player.name, "team": team.name})

        # Suspension and injury countdown
        for team in self.teams:
            for player in team.squad:
                if player.suspension_matches_left > 0:
                    player.suspension_matches_left -= 1
                    if player.suspension_matches_left == 0:
                        player.is_suspended = False
                if player.injury_matches_left > 0:
                    player.injury_matches_left -= 1
                    if player.injury_matches_left == 0:
                        player.is_injured      = False
                        player.injury_severity = None

        # Off-match injury roll
        new_injuries = []
        for team in self.teams:
            for player in team.squad:
                if not player.is_injured and random.random() < 0.01:
                    severity, matches_out = roll_injury_severity()
                    player.is_injured          = True
                    player.injury_matches_left = matches_out
                    player.injury_severity     = severity
                    player.career_injuries    += 1
                    self.calendar.schedule_injury_notification(
                        player, team, self.calendar.current_date
                    )
                    new_injuries.append({
                        "player":   player.name,
                        "team":     team.name,
                        "severity": severity,
                        "matches":  matches_out,
                    })

        # In-match injuries
        for result in recent:
            for inj_evt in [e for e in result.get("events", []) if e["type"] == "injury"]:
                player, team_name = find_player(
                    self.teams,
                    player_id=inj_evt.get("player_id"),
                    name=inj_evt.get("player"),
                    team_name=inj_evt.get("team"),
                )
                if player:
                    team = next(t for t in self.teams if t.name == team_name)
                    self.calendar.schedule_injury_notification(
                        player, team, self.calendar.current_date
                    )

        # Low-morale player meetings
        for team in self.teams:
            for player in team.squad:
                if player.morale < -2.0:
                    self.calendar.schedule_player_meeting(
                        player, team, self.calendar.current_date
                    )

        # Newspaper story (probabilistic)
        self.calendar.generate_newspaper_story(self.teams, self.comp)

        # Persist
        save_competition_to_file(self.comp, self.calendar.current_date)

        # Next event date (for the view to display)
        next_event = self.calendar.get_next_event_date(
            self.calendar.current_date + datetime.timedelta(days=1)
        )

        return {
            "type":               "matchday",
            "season":             self.season_year,
            "date":               self.calendar.current_date.isoformat(),
            "matchday_num":       matchday_num,
            "competition":        self.comp.name,
            "results":            recent,
            "standings":          self._serialise_standings(),
            "scheduled_replays":  scheduled_replays,
            "newly_suspended":    newly_suspended,
            "new_injuries":       new_injuries,
            "next_event_date":    next_event.isoformat() if next_event else None,
        }

    # ── Season end ────────────────────────────────────────────────────────────

    def _finalise_season(self) -> dict:
        """
        Called when the calendar has no more events.
        Computes final stats, awards the trophy, calls end_season(), and
        returns a SEASON_END state dict. Does NOT advance to the next season
        yet — that happens on the next advance() call so the view can show
        final stats first.
        """
        all_players = [p for t in self.teams for p in t.squad]

        top_scorers = sorted(all_players, key=lambda p: p.goals, reverse=True)[:10]
        top_assisters = sorted(all_players, key=lambda p: p.assists, reverse=True)[:10]
        top_clean_sheets = sorted(
            [p for p in all_players if p.position == "GK"],
            key=lambda p: p.clean_sheets, reverse=True
        )[:10]
        top_rated = sorted(
            [p for p in all_players if p.season_rating_appearances >= 5],
            key=lambda p: p.season_avg_rating, reverse=True
        )[:10]

        sorted_table = self._sorted_standings()
        champion_name = sorted_table[0][0]

        # Trophy
        for team in self.teams:
            if team.name == champion_name:
                team.trophies.append({
                    "competition": self.comp.name,
                    "season":      self.season_year,
                })
                for player in team.squad:
                    player._won_trophy_flag = True
                    player.career_trophies += 1
                    player.career_trophies_by_comp[self.comp.name] = (
                        player.career_trophies_by_comp.get(self.comp.name, 0) + 1
                    )

        # Records
        self.record_book.finalize_season(self.comp, self.teams, self.season_year)

        # End season (rolls stats into career, resets season counters)
        self.current_season.end_season()
        self._season_complete = True

        # Clean up save file
        if os.path.exists("competition_data.json"):
            os.remove("competition_data.json")

        def _player_rows(players):
            return [
                {
                    "name":   p.name,
                    "team":   next(t.name for t in self.teams if p in t.squad),
                    "goals":  p.goals,
                    "assists": p.assists,
                    "clean_sheets": p.clean_sheets,
                    "avg_rating":   round(p.season_avg_rating, 2),
                }
                for p in players
            ]

        return {
            "type":              "season_end",
            "season":            self.season_year,
            "date":              self.calendar.current_date.isoformat(),
            "champion":          champion_name,
            "final_standings":   self._serialise_standings(),
            "top_scorers":       _player_rows(top_scorers),
            "top_assisters":     _player_rows(top_assisters),
            "top_clean_sheets":  _player_rows(top_clean_sheets),
            "top_rated":         _player_rows(top_rated),
        }

    # ── Between seasons ───────────────────────────────────────────────────────

    def _advance_between_seasons(self) -> dict:
        """
        Called after SEASON_END has been shown.
        Ages players, saves, and either starts the next season or ends the game.
        """
        # Save after season
        save_teams_to_file(self.teams)
        save_records_to_file(self.record_book)

        # Player development
        development_log = []
        for team in self.teams:
            for player in team.squad:
                old_ca = player.current_ability
                player.start_new_season()
                ca_change = player.current_ability - old_ca
                if abs(ca_change) >= 2:
                    development_log.append({
                        "player":    player.name,
                        "team":      team.name,
                        "old_ca":    old_ca,
                        "new_ca":    player.current_ability,
                        "direction": "up" if ca_change > 0 else "down",
                    })

        self._season_index   += 1
        self._season_complete = False

        if self._season_index >= self.num_seasons:
            return {
                "type":            "game_over",
                "seasons_played":  self.num_seasons,
                "development_log": development_log,
            }

        # Start the next season
        self._start_season()

        return {
            "type":            "between_seasons",
            "completed_season": self._season_label(self._season_index - 1),
            "next_season":      self.season_year,
            "development_log":  development_log,
        }

    # ── Blocking event state ──────────────────────────────────────────────────

    def _state_blocking_event(self, event) -> dict:
        """
        Return a BLOCKING_EVENT state dict for a pending non-match event.

        Schema:
            type:        "blocking_event"
            season:      str
            date:        str  (ISO)
            event_id:    str
            category:    str
            title:       str
            description: str
            choices:     list of {"index": int, "text": str}
                         empty list means acknowledgement-only
        """
        return {
            "type":        "blocking_event",
            "season":      self.season_year,
            "date":        self.calendar.current_date.isoformat(),
            "event_id":    event.id,
            "category":    event.category,
            "title":       event.title,
            "description": event.description,
            "choices": [
                {"index": i, "text": c.text}
                for i, c in enumerate(event.choices)
            ],
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _season_label(self, index: int) -> str:
        year = self.start_year + index
        return f"{year}/{str(year + 1)[-2:]}"

    def _sorted_standings(self) -> list:
        return sorted(
            self.comp.standings.items(),
            key=lambda x: (
                -x[1]["points"],
                -x[1]["goal_difference"],
                -x[1]["goals_for"],
                x[0],
            ),
        )

    def _serialise_standings(self) -> list:
        """Return standings as a list of dicts, sorted, for easy rendering."""
        return [
            {"team": name, **stats}
            for name, stats in self._sorted_standings()
        ]