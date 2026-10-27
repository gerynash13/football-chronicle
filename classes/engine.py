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
import secrets
from rng import rng
import datetime

try:
    # Local project structure — classes is a package
    from classes import Team, Player, Competition, Season
    from classes.competition import CupCompetition, SupercupCompetition
except ModuleNotFoundError:
    # Flat structure (test environment)
    from team import Team
    from player import Player
    from competition import Competition, CupCompetition, SupercupCompetition
    from season import Season
from data_manager import (
    save_teams_to_file,
    load_teams_from_file,
    save_competition_to_file,
    load_competition_data,
    save_records_to_file,
    load_records_from_file,
    save_world_state,
    load_world_state,
)
from data_loader import (
    load_nations,
    teams_in_competition,
    competitions_for_season,
    journalists_for_season,
    get_nation,
    TeamConfig,
    load_competitions,
    teams_for_season,
)
from news_feed import (
    NewsFeed,
    publish_match_result,
    publish_hat_trick,
    publish_competition_winner,
    publish_record_broken,
)
from newsroom import (
    ArticleStore,
    Article,
    write_article,
    covers_event,
    MATCH_REPORT_TEMPLATES,
)
from records import RecordBook
from player_refs import find_player
from name_generator import generate_squad
from events import Event, Choice
from game_calendar import GameCalendar, apply_effects, apply_match_morale
from rules import get_max_subs, get_yellow_threshold, get_match_days, get_card_bucket
from simulation import roll_injury_severity
from availability import tick_suspensions, heal_injuries
from save_slot import SaveSlot, ENGINE_VERSION
from match_model import OFF_MATCH_INJURY_RATE, INJURY_DAYS_PER_MATCH
import lifecycle
from facilities import facilities_from_config
from archive import Archive, build_payload, leaderboard_rows


class GameEngine:

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, start_year=1896, num_seasons=3, seed=None, slot=None):
        self.start_year  = start_year
        self.num_seasons = num_seasons
        self.seed = seed if seed is not None else secrets.randbelow(2**32)
        self.slot = slot or SaveSlot("default")

        # Persisted across seasons
        self.teams:       list       = []
        self.record_book: RecordBook = RecordBook()
        self.news_feed:   NewsFeed   = NewsFeed()
        self.newsroom:    ArticleStore = ArticleStore()

        # Per-season objects, set in _start_season()
        self.season_year:    str         = ""
        self.current_season: Season      = None
        self.comp:           Competition = None
        self.cup:            object = None
        self.calendar:       GameCalendar = None

        # Internal bookkeeping
        self._season_index:   int  = 0       # which season we're on (0-based)
        self._last_processed: datetime.date = None
        self._pending_event   = None         # blocking non-match event awaiting choice
        self._season_complete: bool = False  # True once end_season() has been called
        self.managed_team: str | None = None
        self._tier_seasons: dict = {}     # Tracks which seasons each tier has been competed in, for prestige calculations
        self._committed_tiers: dict = {}   # Tracks which tiers the player has committed to, for prestige calculations
        self.archive = None
        self._pending_archive = None
        
        # Previous season's results - used by _start_season() to resolve supercup participants.
        # Populated at the end of _finalise_season().
        self._prev_league_winner:       str | None = None
        self._prev_league_runner_up:    str | None = None
        self._prev_cup_winner:          str | None = None
        self._prev_cup_runner_up:       str | None = None
        
        self._replaying = False
        self._manifest_version = ENGINE_VERSION
        
    def _log_action(self, action: dict):
        if not self._replaying:
            self.slot.append_action(action)
        
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
        
        self._log_action({"op": "advance"})

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
        if event.category == "setup":
            if index < 0 or index >= len(event.choices):
                return {
                    "type":    "error",
                    "message": f"Invalid choice. Pick 0–{len(event.choices) - 1}.",
                }
            chosen = event.choices[index]
            team = next((t for t in self.teams if t.name == chosen.text), None)
            # Resolve name → Team object so the rest of the engine
            # can compare by identity rather than string matching
            self.managed_team = team.name if team else None
            self._save_world()
            event.resolution = chosen.text
            event.is_read    = True
            self._pending_event = None
            return self._advance_calendar()

        if not event.choices:
            # Acknowledgement-only event — any input dismisses it
            self._log_action({"op": "choose", "index": index})
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
        self._log_action({"op": "choose", "index": index})
        apply_effects(chosen.effects, self.teams)
        event.resolution = chosen.text
        event.is_read    = True
        self._pending_event = None
        return self._advance_calendar()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _initialise(self, load_save: bool) -> dict:
        """Load or generate teams, then start the first season."""
        self._nations = load_nations()
        
        resuming = load_save and self.slot.exists()
        if resuming:
            m = self.slot.read_manifest()
            self.seed, self._season_index, self.managed_team = (
                m["seed"], m["season_index"], m["managed_team"])
            self._manifest_version = m.get("engine_version")
        else:
            self.slot.reset() # New Game wipes the slot
            
        rng.seed(f"{self.seed}: setup")
        self.archive: Archive = Archive(self.slot.path("archive.sqlite"))
        self.archive.init()
        
        self.record_book = load_records_from_file(self.slot.path("records_data.json"))
        self._tier_seasons, self._committed_tiers, prev = load_world_state(
            self._nations, self.slot.path("world_state.json"))
        self._prev_league_winner = prev.get("league_winner")
        self._prev_league_runner_up = prev.get("league_runner_up")
        self._prev_cup_winner = prev.get("cup_winner")
        self._prev_cup_runner_up = prev.get("cup_runner_up")
        
        if resuming:
            self.teams = load_teams_from_file(self.slot.path("teams_data.json"))
        else:
            self.teams = []
            
        self._start_season()
        
        if self.managed_team is None:
            self._pending_event = self._build_team_selection_event()
            return self._state_blocking_event(self._pending_event)
        return self._replay_saved_actions()

    def _replay_saved_actions(self) -> dict:
        version_ok = self._manifest_version == ENGINE_VERSION
        actions = self.slot.read_actions() if version_ok else []
        if not version_ok:
            self.slot.clear_actions()      # old moves would replay differently
        state = {
            "type": "resumed", "season": self.season_year,
            "date": self.calendar.current_date.isoformat(),
            "managed_team": self.managed_team,
            "replayed_actions": len(actions),
            "version_mismatch": not version_ok,
        }
        self._replaying = True
        try:
            for a in actions:
                state = self.advance() if a["op"] == "advance" else self.choose(a["index"])
        finally:
            self._replaying = False
        return state

    def _build_team_selection_event(self) -> Event:
        choices = [Choice(text=team.name) for team in sorted(self.teams, key=lambda t: t.name)]
        return Event(
            date=self.calendar.current_date,
            category="setup",
            blocking=True,
            title="Choose your club",
            description=(
                "Select the team you will manage for this season. "
                "Your choice will shape the club-level story and inbox as gameplay expands."
            ),
            choices=choices,
        )

    def _load_squad_file(self, season_year: str) -> dict:
        """
        Load data/squads/<season_year>.yaml if it exists.
        Returns a dict keyed by team_id, or empty dict if file not found.

        The season_year "1896/97" maps to the filename "1896_97.yaml".
        """
        import yaml
        filename = season_year.replace("/", "_") + ".yaml"
        # The data/ directory lives at the project root. When this module
        # is located inside the `classes` package, __file__ points to
        # classes/engine.py — so walk up one level to reach the project root.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(project_root, "data", "squads", filename)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _build_squad_from_yaml(self, players_data: list) -> list:
        """
        Build a list of Player objects from a squad YAML entry.

        Expected shape per player:
            name:               str
            position:           GK | DEF | MID | FWD
            birth_year:         int   (engine picks a random day/month)
            current_ability:    int
            potential_ability:  int
            nationality:        str   (nation_id, optional — defaults to team nation)
            parent_nationality: str   (nation_id, optional)
            preferred_foot:     str   (optional — randomly assigned if absent)
            contract_expires:   int   (season start year, optional)
            wage:               int   (optional)
        """
        import datetime
        squad = []
        for p in players_data:
            birth_year = p.get("birth_year")
            if birth_year:
                birth_date = datetime.date(
                    int(birth_year),
                    rng.randint(1, 12),
                    rng.randint(1, 28),
                )
            else:
                # Fallback: derive birth year from age if provided
                age = p.get("age", 25)
                start_year = int(self.season_year.split("/")[0])
                birth_date = datetime.date(
                    start_year - age,
                    rng.randint(1, 12),
                    rng.randint(1, 28),
                )

            player = Player(
                name               = p["name"],
                position           = p["position"],
                birth_date         = birth_date,
                current_ability    = p["current_ability"],
                potential_ability  = p["potential_ability"],
                nationality        = p.get("nationality"),
                parent_nationality = p.get("parent_nationality"),
                preferred_foot     = p.get("preferred_foot"),
                contract_expires   = p.get("contract_expires"),
                wage               = p.get("wage", 0),
            )
            squad.append(player)
        return squad

    def _start_season(self):
        """Initialise all per-season objects."""
        self.season_year = self._season_label(self._season_index)
        self._season_complete = False
        
        # New clubs get their own dice stream. Then we reshuffle, so the rest of the season
        # starts from the same place whether or not clubs were just founded. That keeps
        # a resumed game identical to the original.
        rng.seed(f"{self.seed}: {self._season_index}:founding")
        newcomers = self._found_new_clubs(self.season_year)
        if newcomers:
            self._seed_youth(newcomers)
        rng.seed(f"{self.seed}: {self._season_index}")
        
        self.current_season = Season(self.season_year, self.teams)
        self._journalist_roster = journalists_for_season(self.season_year)
        self.calendar = GameCalendar(self.season_year)
        available_days = get_match_days(self.season_year)
        
        # Competitions come from the YAML; leagues are scheduled first
        configs = sorted(competitions_for_season(self.season_year), key=lambda c: c.type != "league")
        self.competitions = []
        for cfg in configs:
            comp = self._build_competition(cfg)
            if comp is None:
                continue
            self.competitions.append(comp)
            self.current_season.add_competition(comp)
            day = available_days[1] if cfg.match_day == "midweek" and len(available_days) > 1 else available_days[0]
            self.calendar.schedule_fixtures(comp, preferred_day=day)
            
        self.comp = next((c for c in self.competitions if c.type == "league"), None)
        self.cup = next((c for c in self.competitions if c.type == "cup"), None)
        self._last_processed = self.calendar.current_date
        
    # Pre-season supercup helpers
    
    def _setup_preseason_supercups(self, comp_configs: dict, primary_day: int):
        """
        For every supercup with timing=pre_season that should run this season,
        resolve participants from last season's stored results and schedule the
        fixture at the very start of the calendar (before league matchday 1).
 
        Called from _start_season().  Adds the competition to self.competitions
        so _process_matchday() picks it up automatically.
 
        Why here and not in _finalise_season()?
        The supercup belongs to the NEW season — its trophy, stats, and fixture
        are all recorded under the season that is about to start.  Resolving
        participants here (at season start) rather than at season end keeps the
        ownership unambiguous.
        """
        start_year = int(self.season_year.split("/")[0])
        for cfg in comp_configs.values():
            if cfg.type != "supercup":
                continue
            if cfg.timing != "pre_season":
                continue
            if cfg.founded_year > start_year:
                continue
            years_since = start_year - cfg.founded_year
            if cfg.frequency > 1 and years_since % cfg.frequency != 0:
                continue # Used for competitions that only run every X years
            
            participants = self._resolve_supercup_participants(cfg)
            if participants is None:
                # Not enough teams - skip silently this season
                # (happens on the first edition of a supercup)
                continue
            
            sc = SupercupCompetition(
                cfg.name,
                participants,
                draw_rules=cfg.draw_rules,
                max_subs=get_max_subs(self.season_year),
                season_year=self.season_year,
                prestige=cfg.prestige,
            )
            sc.generate_fixtures()
            self.current_season.add_competition(sc)
            self.competitions.append(sc)
            
            # Schedule the supercup on the first available day of the season, 
            # before any league fixture. We pick the primary matchday so it 
            # lands on a whatever the era's primary day is.
            self._schedule_supercup_fixture(sc, primary_day)
            
    def _resolve_supercup_participants(self, cfg) -> list | None:
        """
        Walk the slots list from the YAML config and look up each team from
        last season's stored results.  If two slots resolve to the same club,
        work through the fallbacks list until a distinct replacement is found.
 
        Returns a list of exactly 2 Team objects, or None if resolution fails.
 
        Why a fallback list in YAML rather than hardcoded logic?
        Different nations' supercups have different rules for this situation.
        Spain replaces the cup slot with the cup runner-up; some countries use
        the league runner-up; others cancel.  Encoding the priority order in
        the data file means Python never needs to know which country's rules
        apply.
        """
        # Build a quick lookup from competition_id -> last season's result map
        result_map = {
            self.comp.name: {
                "winner": self._prev_league_winner,
                "runner_up": self._prev_league_runner_up,
            }
        }
        if self.cup:
            result_map[self.cup.name] = {
                "winner": self._prev_cup_winner,
                "runner_up": self._prev_cup_runner_up,
            }
            
        # Also index by competition_id (YAML key) for direct lookup
        # comp_configs is not in scope here, so we use a name-to-id mapping
        # built from self.competitions.
        id_to_name = {}
        for comp in self.competitions:
            # The competition is comes from YAML - match by the name we stored
            # A future multi-nation generalization can carry the id on the
            # Competition object itself.
            pass
        
        def _lookup_slot(slot: dict) -> str | None:
            """Return a team name for a given slot dict, or None"""
            source_id = slot.get("source", "")
            role = slot.get("role", "winner")
            # Match source_id against known competition names/ids
            # Current mapping: prote_kategorias -> league, protonas_cup -> cup
            # When we generalize to multi-nation this will read from a registry
            source_map = {
                "prote_kategorias": self.comp.name,
                "protonas_cup": self.cup.name if self.cup else None,
            }
            comp_name = source_map.get(source_id)
            if comp_name is None:
                return None
            return result_map.get(comp_name, {}).get(role)
        
        slots = cfg.participants.get("slots", [])
        fallbacks = cfg.participants.get("fallbacks", [])
        
        resolved: list[str] = []
        for slot in slots:
            name = _lookup_slot(slot)
            if name is None:
                return None # source competition result unavailable
            if name not in resolved:
                resolved.append(name)
            else:
                # Conflict: same club in two slots, try fallbacks in order
                replaced = False
                for fb in fallbacks:
                    candidate = _lookup_slot(fb)
                    if candidate and candidate not in resolved:
                        resolved.append(candidate)
                        replaced = True
                        break
                if not replaced:
                    return None # No distinct replacement found
                
        if len(resolved) != 2:
            return None
        
        # Convert names to team objects
        team_map = {t.name: t for t in self.teams}
        team_objs = [team_map.get(n) for n in resolved]
        if any(t is None for t in team_objs):
            return None
        
        return team_objs
    
    def _schedule_supercup_fixture(self, sc: SupercupCompetition, preferred_day:int):
        """
        Place the supercup on the first available match-day at the very start
        of the season calendar, before the league's opening round.
 
        We walk forward from season_start looking for the first occurrence of
        preferred_day that isn't already occupied.
        """
        from datetime import timedelta
        occupied = {e.date for e in self.calendar.scheduled_events if e.category == "match"}
        candidate = self.calendar.season_start
        # Advance to the first preferred weekday
        while candidate.weekday() != preferred_day:
            candidate += timedelta(days=1)
        # Skip any already-occupied days
        while candidate in occupied:
            candidate += timedelta(weeks=1)
        
        for fixture in sc.fixtures:
            fixture["date"] = candidate
            
        from events import Event
        self.calendar.add_event(Event(
            date=candidate,
            category="match",
            blocking=True,
            title=f"{sc.name}",
            description=(
                f"{sc.fixtures[0]['home_team'].name} vs {sc.fixtures[0]['away_team'].name} ({sc.name})"
            )
        ))
        
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
            d = self._last_processed + datetime.timedelta(days=1)
            while d <= next_date:
                if d.weekday() == 0:
                    self.calendar.apply_weekly_decay(self.teams)
                d += datetime.timedelta(days=1)

            self.calendar.current_date = next_date
            heal_injuries(self.teams, next_date)
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
        Simulate all matches for today across all active competitions, 
        run post-match logic, and return a MATCHDAY state dict.

        This is the largest chunk of logic extracted from main.py.
        Every side-effect (stat updates, morale, injuries, suspensions,
        saves) happens here. The returned dict contains all the data the
        view needs to render results, standings, and notifications.
        """
        today = self.calendar.current_date
        
        # Find which competitions have fixtures today
        active_comp = None
        today_fixtures = []
        for comp in getattr(self, 'competitions', [self.comp, self.cup]):
            fixtures = [f for f in comp.fixtures if f.get("date") == today]
            if fixtures:
                active_comp = comp
                today_fixtures = fixtures
                break # Only one competition can have fixtures today
        
        if not today_fixtures:
            return self._advance_calendar()

        matchday_num = today_fixtures[0]["matchday"]
        if matchday_num in active_comp.completed_matchdays:
            return self._advance_calendar()

        active_comp.current_matchday = matchday_num
        
        # Who was already out before this match? Only they serve a match today
        playing_names = {f[side].name for f in today_fixtures
                         for side in ("home_team", "away_team")}
        sitting_out = [
            p for t in self.teams if t.name in playing_names for p in t.squad
            if p.suspension_matches_left > 0
        ]

        # Simulate
        if active_comp.type == "cup":
            drawn_fixtures = active_comp.simulate_cup_round()
        elif active_comp.type == "supercup":
            drawn_fixture = active_comp.simulate_supercup()
            drawn_fixtures = [drawn_fixture] if drawn_fixture else []
        else:
            active_comp.simulate_matchday()
            drawn_fixtures = []

        recent = active_comp.results[-len(today_fixtures):]
        for r in recent:
            r["date"] = today.isoformat()
            r.setdefault("matchday", matchday_num)

        matchday_events = []
        
        # Record-book and morale updates
        for result in recent:
            self.record_book.process_match(
                result,
                self.teams,
                competition_name=active_comp.name,
                season_year=self.season_year,
                match_date=self.calendar.current_date
            )
            home_team = next((t for t in self.teams if t.name == result["home_team"]), None)
            away_team = next((t for t in self.teams if t.name == result["away_team"]), None)
            if home_team and away_team:
                apply_match_morale(home_team, away_team, result["home_goals"], result["away_goals"])

            scorers = [
                {"player_id": e.get("player_id"), "player": e.get("player"), "team": e.get("team"), "minute": e.get("minute")}
                for e in result.get("events", []) if e.get("type") == "goal"
            ]
            # ── News feed: match result ───────────────────────────────────────
            event = publish_match_result(
                self.news_feed,
                competition = active_comp.name,
                home_team   = result["home_team"],
                away_team   = result["away_team"],
                home_goals  = result["home_goals"],
                away_goals  = result["away_goals"],
                date        = self.calendar.current_date,
                season      = self.season_year,
                home_region = home_team.home_region if home_team else "",
                away_region = away_team.home_region if away_team else "",
                matchday    = matchday_num,
                scorers     = scorers,
                relevance   = ["local"],
            )
            matchday_events.append(event)
            
            # ── News feed: hat tricks ─────────────────────────────────────────
            from collections import Counter
            goal_events  = [e for e in result.get("events", []) if e["type"] == "goal"]
            goals_by_pid: Counter = Counter()
            pid_to_name:  dict    = {}
            for evt in goal_events:
                pid = evt.get("player_id") or evt.get("player", "")
                goals_by_pid[pid] += 1
                pid_to_name[pid] = evt.get("player", "")
            for pid, count in goals_by_pid.items():
                if count >= 3:
                    ht_event = publish_hat_trick(
                        self.news_feed,
                        player      = pid_to_name[pid],
                        player_id   = pid,
                        team        = result["home_team"] if any(
                            e.get("player_id") == pid and e["team"] == result["home_team"]
                            for e in goal_events
                        ) else result["away_team"],
                        goals       = count,
                        competition = active_comp.name,
                        match       = (f"{result['home_team']} {result['home_goals']}"
                                       f"-{result['away_goals']} {result['away_team']}"),
                        date        = self.calendar.current_date,
                        season      = self.season_year,
                        relevance   = ["local", "regional"],
                    )
                    matchday_events.append(ht_event)
                    
        for event in matchday_events:
            for journalist in self._journalist_roster:
                if covers_event(journalist, event, self.teams):
                    article = write_article(journalist, event, self.season_year)
                    if article:
                        self.newsroom.publish(article)
                    
        # Cup: schedule replays for draws
        scheduled_replays = []
        for drawn in drawn_fixtures:
            replay_date = self.calendar.schedule_replay(
                active_comp,
                drawn,
                self.calendar.current_date,
            )
            if replay_date:
                scheduled_replays.append({
                    "home_team": drawn["home_team"].name,
                    "away_team": drawn["away_team"].name,
                    "date":      replay_date.isoformat(),
                })

        # After every cup matchday check if the round is complete and build the next one
        if active_comp.type == "cup":
            if active_comp.build_next_round():
                available_days = get_match_days(self.season_year)
                cup_day = available_days[1] if len(available_days) > 1 else available_days[0]
                self.calendar.schedule_cup_next_round(active_comp, preferred_day=cup_day)

        # Yellow card accumulation → suspensions
        yellow_threshold = get_yellow_threshold(self.season_year)
        newly_suspended  = []
        bucket = get_card_bucket(active_comp.name)
        for team in self.teams:
            for player in team.squad:
                count = player.yellow_cards_by_comp.get(bucket, 0)
                if count > 0 and count % yellow_threshold == 0 and not player.is_suspended:
                    player.is_suspended = True
                    player.suspension_matches_left = 1
                    player.yellow_cards_by_comp[bucket] = count - yellow_threshold
                    newly_suspended.append({"player": player.name, "team": team.name})

        # Suspension and injury countdown
        tick_suspensions(sitting_out)

        # Off-match injury roll
        new_injuries = []
        for team in self.teams:
            for player in team.squad:
                if not player.is_injured and rng.random() < OFF_MATCH_INJURY_RATE:
                    severity, matches_out = roll_injury_severity()
                    player.is_injured          = True
                    player.injury_matches_left = matches_out
                    player.injury_severity     = severity
                    player.injury_until        = self.calendar.current_date + datetime.timedelta(
                        days=INJURY_DAYS_PER_MATCH * matches_out
                    )
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
                    player_injury_until = self.calendar.current_date + datetime.timedelta(
                        days=INJURY_DAYS_PER_MATCH * inj_evt["matches_out"]
                    )
                    player.injury_until = player_injury_until
                    self.calendar.schedule_injury_notification(
                        player, team, self.calendar.current_date
                    )

        # Low-morale player meetings
        for team in self.teams:
            if team.name != self.managed_team:
                continue
            for player in team.squad:
                if player.morale < -2.0:
                    self.calendar.schedule_player_meeting(
                        player, team, self.calendar.current_date
                    )

        # Newspaper story (probabilistic)
        self.calendar.generate_newspaper_story(self.teams, active_comp)

        # Next event date (for the view to display)
        next_event = self.calendar.get_next_event_date(
            self.calendar.current_date + datetime.timedelta(days=1)
        )

        # Identify the user's own result this matchday (if any)
        your_result = None
        if self.managed_team:
            your_result = next(
                (r for r in recent
                 if self.managed_team in ([r["home_team"], r["away_team"]])),
                None,
            )

        return {
            "type":               "matchday",
            "season":             self.season_year,
            "date":               self.calendar.current_date.isoformat(),
            "matchday_num":       matchday_num,
            "competition":        active_comp.name,
            "competition_type":   active_comp.type,
            "results":            recent,
            "standings":          self._serialise_standings() if active_comp.type == "league" else None,
            "cup_bracket":        self.get_cup_bracket() if active_comp.type == "cup" else None,
            "scheduled_replays":  scheduled_replays,
            "newly_suspended":    newly_suspended,
            "new_injuries":       new_injuries,
            "next_event_date":    next_event.isoformat() if next_event else None,
            "managed_team":       self.managed_team,
            "your_result":        your_result,
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
        
        # Get cup winner (if cup is complete)
        cup_winner_name = None
        if self.cup and self.cup.results:
            max_matchday = max((f["matchday"] for f in self.cup.fixtures), default=0)
            final_results = [r for r in self.cup.results if r.get("matchday") == max_matchday]
            if final_results:
                final_result = final_results[-1]  # Should only be one final
                if final_result["home_goals"] > final_result["away_goals"]:
                    cup_winner_name = final_result["home_team"]
                elif final_result["away_goals"] > final_result["home_goals"]:
                    cup_winner_name = final_result["away_team"]
                    
        # Derive cup runner-up from the final fixture.
        cup_runner_up_name = None
        if cup_winner_name and self.cup and self.cup.fixtures:
            max_matchday = max((f["matchday"] for f in self.cup.fixtures), default=0)
            final_fixtures = [
                f for f in self.cup.fixtures
                if f["matchday"] == max_matchday and not f.get("is_replay")
            ]
            if final_fixtures:
                ff = final_fixtures[-1]
                home_name = ff["home_team"].name
                away_name = ff["away_team"].name
                cup_runner_up_name = away_name if cup_winner_name == home_name else home_name
                
        # Store season's results so _start_season() can resolve pre-season supercup
        # participants for next season.
        self._prev_league_winner = champion_name
        self._prev_league_runner_up = sorted_table[1][0] if len(sorted_table) > 1 else None
        self._prev_cup_winner = cup_winner_name
        self._prev_cup_runner_up = cup_runner_up_name

        # Trophy — League
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
        
        # Trophy — Cup
        if cup_winner_name:
            for team in self.teams:
                if team.name == cup_winner_name:
                    team.trophies.append({
                        "competition": self.cup.name,
                        "season":      self.season_year,
                    })
                    for player in team.squad:
                        player._won_trophy_flag = True
                        player.career_trophies += 1
                        player.career_trophies_by_comp[self.cup.name] = (
                            player.career_trophies_by_comp.get(self.cup.name, 0) + 1
                        )

        # Records
        self.record_book.finalize_season(
            self.comp, [t for t in self.teams if t.name in self.comp.standings], self.season_year
        )

        # Snapshot leaderboard rows BEFORE end_season() resets season stats
        def _player_rows(players):
            return [
                {
                    "name":         p.name,
                    "team":         next(t.name for t in self.teams if p in t.squad),
                    "goals":        p.goals,
                    "assists":      p.assists,
                    "clean_sheets": p.clean_sheets,
                    "avg_rating":   round(p.season_avg_rating, 2),
                }
                for p in players
            ]

        season_end_state = {
            "type":             "season_end",
            "season":           self.season_year,
            "date":             self.calendar.current_date.isoformat(),
            "champion":         champion_name,
            "cup_winner":       cup_winner_name,
            "final_standings":  self._serialise_standings(),
            "top_scorers":      _player_rows(top_scorers),
            "top_assisters":    _player_rows(top_assisters),
            "top_clean_sheets": _player_rows(top_clean_sheets),
            "top_rated":        _player_rows(top_rated),
        }
        
        ids = {t.name: t.id for t in self.teams}
        runner_up_name = sorted_table[1][0] if len(sorted_table) > 1 else None
        trophies = [{
            "season": self.season_year, "competition": self.comp.key or self.comp.name,
            "winner_id": ids[champion_name], "winner": champion_name,
            "runner_up_id": ids.get(runner_up_name), "runner_up": runner_up_name,
        }]
        if cup_winner_name:
            trophies.append({
                "season": self.season_year, "competition": self.cup.key or self.cup.name,
                "winner_id": ids[cup_winner_name], "winner": cup_winner_name,
                "runner_up_id": ids.get(cup_runner_up_name), "runner_up": cup_runner_up_name,
            })
        self._pending_archive = build_payload(
            self.season_year, self.calendar.season_end, self.teams, self.competitions,
            trophies,
            leaderboard_rows(self.season_year, self.teams, {
                "goals": top_scorers, "assists": top_assisters,
                "clean_sheets": top_clean_sheets, "avg_rating": top_rated}))

        # End season (rolls stats into career, resets season counters)
        self.current_season.end_season()
        self._season_complete = True

        return season_end_state
    
    def _save_world(self):
        save_teams_to_file(self.teams, self.slot.path("teams_data.json"))
        save_records_to_file(self.record_book, self.slot.path("records_data.json"))
        save_world_state(
            self._nations, self._tier_seasons, self._committed_tiers,
            prev_season_results={
                "league_winner":    self._prev_league_winner,
                "league_runner_up": self._prev_league_runner_up,
                "cup_winner":       self._prev_cup_winner,
                "cup_runner_up":    self._prev_cup_runner_up,
            },
            filename=self.slot.path("world_state.json"),
        )
        self.slot.write_manifest(
            seed=self.seed, start_year=self.start_year,
            season_index=self._season_index, managed_team=self.managed_team,
            engine_version=ENGINE_VERSION,
        )
        self.slot.clear_actions()

    # ── Between seasons ───────────────────────────────────────────────────────

    def _advance_between_seasons(self) -> dict:
        """
        Called after SEASON_END has been shown.
        Ages players, saves, and either starts the next season or ends the game.
        """
        from prestige import collect_upset_bonuses, update_team_prestige, update_nation_prestige
        
        # Save after season
        
        standings = self._serialise_standings()
        league_teams = [t for t in self.teams if t.name in self.comp.standings]
        upset_bonuses = collect_upset_bonuses(self.comp.results, league_teams)
        prestige_log = update_team_prestige(league_teams, standings, self.comp.prestige, upset_bonuses)
        
        nation_log = update_nation_prestige(
            self._nations,
            self.teams,
            standings,
            self.comp.prestige,
            self._tier_seasons,
            self._committed_tiers,
        )

        # Player development
        development_log = []
        for team in self.teams:
            for player in team.squad:
                old_ca = player.current_ability
                player.start_new_season(self.calendar.season_end)
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
        
        # Lifecycle: retire, promote, release, new academy intake
        completed_label = self._season_label(self._season_index - 1)
        next_label = self._season_label(self._season_index)
        on_date = self.calendar.season_end
        league_lvl = lifecycle.league_level(self._league_teams())
        retirement_log = []
        for team in self.teams:
            for p in team.youth:
                p.start_new_season(on_date)
            retired = lifecycle.retire_players(team, completed_label)
            promoted = lifecycle.ai_promotions(team, on_date)
            released = lifecycle.release_overage(team, on_date)
            cfg = self._nations[team.nation_id].to_player_config()
            arrivals = lifecycle.youth_intake(team, cfg, league_lvl, next_label)
            retirement_log.append({
                "team": team.name,
                "retired":  [p.name for p in retired],
                "promoted": [p.name for p in promoted],
                "released": [p.name for p in released],
                "arrived":  [p.name for p in arrivals],
            })
        
        if self._pending_archive is not None:
            self.archive.write_season(self._pending_archive)
            self._pending_archive = None

        self._save_world()

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
            "prestige_log":     prestige_log,
            "nation_log":       nation_log,
            "retirement_log":   retirement_log,
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
            "managed_team": self.managed_team,
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
        
    def _make_team(self, cfg, season_year, squad_data):
        """Build one club from its YAML entry (if there is one)."""
        team = Team(cfg.name, cfg.attack, cfg.midfield, cfg.defense)
        team.id =                  cfg.id
        team.nation_id =           cfg.nation_id
        team.league_nation_id =    cfg.league_nation_id
        team.league_nation_id_year = cfg.league_nation_id_year
        team.prestige =            cfg.prestige
        team.home_region =         cfg.home_region
        team.budget =              cfg.budget
        team.wage_budget =         cfg.wage_budget
        team.competitions =        cfg.competitions
        team.facilities =          cfg.facilities
        if cfg.id in squad_data:
            team.squad = self._build_squad_from_yaml(squad_data[cfg.id])
        else:
            nation = get_nation(cfg.nation_id)
            team.squad = generate_squad(
                cfg.name, average_ca=cfg.avg_ca, nation=nation.name,
                season_year=season_year, home_region=cfg.home_region
            )
        return team
        
    def _found_new_clubs(self, season_year):
        """Create every club that exists by this season but isn't in the world yet."""
        known = {t.id for t in self.teams}
        squad_data = self._load_squad_file(season_year)
        configs = sorted(teams_for_season(season_year), key=lambda c: (c.founded_year, c.id))
        new = [self._make_team(cfg, season_year, squad_data) 
               for cfg in configs if cfg.id not in known]
        self.teams.extend(new)
        return new
    
    def _league_teams(self):
        """Clubs that belong to a league (not just a cup)"""
        league_ids = {c.id for c in load_competitions().values() if c.type == "league"}
        return [t for t in self.teams if league_ids & set(t.competitions)]
    
    def _seed_youth(self, teams):
        """Give brand-new clubs an academy of players."""
        league_lvl = lifecycle.league_level(self._league_teams() or self.teams)
        for team in teams:
            cfg = self._nations[team.nation_id].to_player_config()
            lifecycle.seed_youth(team, cfg, league_lvl, self.season_year)
            
    def _build_competition(self, cfg):
        """One competition for this season, from its YAML entry and the clubs that belong to it."""
        if cfg.type not in ("league", "cup"):
            return None  # Supercup / international tournaments not wired yet
        members = [t for t in self.teams if cfg.id in t.competitions]
        if len(members) < 2:
            return None
        cls = CupCompetition if cfg.type == "cup" else Competition
        comp = cls(cfg.name, members, max_subs=get_max_subs(self.season_year),
                   season_year=self.season_year, prestige=cfg.prestige)
        comp.key = cfg.id
        comp.tier = cfg.tier
        comp.nation_id = cfg.nation_id
        comp.generate_fixtures()
        return comp

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
        ids = {t.name: t.id for t in self.teams}
        return [
            {"team": name, "team_id": ids[name], **stats}
            for name, stats in self._sorted_standings()
        ]
        
    def team_by_id(self, team_id):
        return next((t for t in self.teams if t.id == team_id), None)
        
    def get_cup_bracket(self) -> dict:
        cup = next((c for c in getattr(self, 'competitions', [self.comp, self.cup]) if c.type == "cup"), None)
        if not cup or not cup.fixtures:
            return {"rounds": []}

        from collections import defaultdict
        by_round: dict = defaultdict(list)
        for f in cup.fixtures:
            by_round[f["round"]].append(f)

        total_rounds = cup._total_rounds
        
        def round_label(rn: int) -> str:
            return {1: "Final", 2: "Semi-Finals", 3: "Quarter-Finals",
                    4: "Round of 16", 5: "Round of 32"}.get(total_rounds - rn + 1, f"Round {rn}")

        rounds = []
        for rn in sorted(by_round.keys()):
            originals = [f for f in by_round[rn] if not f.get("is_replay")]
            replays = [f for f in by_round[rn] if f.get("is_replay")]

            fixtures_out = []
            for f in originals:
                home_name = f["home_team"].name
                away_name = f["away_team"].name
                winner = cup._get_decided_winner(f)

                # Find this fixture's result (draw or win)
                result_obj = next(
                    (r for r in cup.results
                     if r["home_team"] == home_name
                     and r["away_team"] == away_name
                     and r.get("round") == rn
                     and not r.get("is_replay", False)),
                    None,
                )
                played = result_obj is not None
                is_draw = played and result_obj["home_goals"] == result_obj["away_goals"]
                has_replay = any(
                    r for r in replays
                    if r["home_team"].name == home_name and r["away_team"].name == away_name
                )

                fixtures_out.append({
                    "home":                 home_name,
                    "away":                 away_name,
                    "home_goals":           result_obj["home_goals"] if played else None,
                    "away_goals":           result_obj["away_goals"] if played else None,
                    "winner":               winner.name if winner else None,
                    "played":               played,
                    "is_draw":              is_draw and not has_replay,
                    "score_display":        (f"{result_obj['home_goals']}-{result_obj['away_goals']}"
                                            + ("r" if is_draw and has_replay else ""))
                                            if played else "vs",
                    "has_pending_replay":   is_draw and has_replay,
                    "is_separator":         False,
                })

            if replays:
                fixtures_out.append({
                    "is_separator": True,
                    "home": None,
                    "away": "Replays",
                    "played": False,
                    "is_draw": False,
                    "score_display": "",
                    "has_pending_replay": False,
                    "home_goals": None,
                    "away_goals": None,
                    "winner": None,
                })

                for f in replays:
                    result_obj = next(
                        (r for r in cup.results
                         if r["home_team"] == f["home_team"].name
                         and r["away_team"] == f["away_team"].name
                         and r.get("round") == rn
                         and r.get("matchday") == f.get("matchday")),
                        None,
                    )
                    played = result_obj is not None
                    fixtures_out.append({
                        "home": f["home_team"].name,
                        "away": f["away_team"].name,
                        "home_goals": result_obj["home_goals"] if played else None,
                        "away_goals": result_obj["away_goals"] if played else None,
                        "winner": f["winner"].name if f["winner"] else None,
                        "played": played,
                        "is_draw": played and result_obj["home_goals"] == result_obj["away_goals"],
                        "score_display": (f"{result_obj['home_goals']}-{result_obj['away_goals']}"
                                          if played else "vs"),
                        "has_pending_replay": False,
                        "is_separator": False,
                    })

            rounds.append({
                "round_num": rn,
                "label": round_label(rn),
                "fixtures": fixtures_out,
            })

        return {"rounds": rounds}
    
    def all_players(self):
        for t in self.teams:
            yield from t.squad
            yield from t.retired
            yield from t.youth
            yield from t.released