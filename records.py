"""
Club, player, goalkeeper, and competition records.

Tracks extremes (single best) and cumulative counters (e.g. career braces).
Transfer-fee records are not implemented (no transfer system yet).
GK "minutes without conceding" is tracked as consecutive clean-sheet matches
for the starting goalkeeper.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from player_refs import (
    build_player_index,
    event_player_id,
    find_player,
    sub_off_id,
    sub_on_id,
)

import datetime


def _scope_all() -> str:
    return "all"


def _scope_team(team_name: str) -> str:
    return f"team:{team_name}"


def _scope_comp(comp_name: str) -> str:
    return f"comp:{comp_name}"


class RecordHolder:
    """A single record entry (best value or snapshot leader)."""

    def __init__(
        self,
        value: Any,
        holder: str,
        *,
        holder_id: str | None = None,
        team: str | None = None,
        season: str | None = None,
        competition: str | None = None,
        detail: str | None = None,
        secondary: str | None = None,
    ):
        self.value = value
        self.holder = holder
        self.holder_id = holder_id
        self.team = team
        self.season = season
        self.competition = competition
        self.detail = detail
        self.secondary = secondary

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "holder": self.holder,
            "holder_id": self.holder_id,
            "team": self.team,
            "season": self.season,
            "competition": self.competition,
            "detail": self.detail,
            "secondary": self.secondary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecordHolder":
        return cls(
            value=data["value"],
            holder=data["holder"],
            holder_id=data.get("holder_id"),
            team=data.get("team"),
            season=data.get("season"),
            competition=data.get("competition"),
            detail=data.get("detail"),
            secondary=data.get("secondary"),
        )

    def __repr__(self) -> str:
        parts = [f"{self.holder}: {self.value}"]
        if self.detail:
            parts.append(f"({self.detail})")
        return " ".join(parts)


class RecordBook:
    """
    Central store for all-time and scoped records.

    extremes:  one best holder per key (e.g. fastest goal, biggest win)
    counters:  running totals per entity (e.g. career braces by player)
    streaks:   in-progress team streaks within a competition season
  comp_champions: consecutive title counts per competition
    """

    def __init__(self):
        self.extremes: dict[str, RecordHolder] = {}
        self.counters: dict[str, dict[str, int]] = defaultdict(dict)
        self.streaks: dict[str, dict[str, Any]] = {}
        self.comp_champions: dict[str, dict[str, int]] = defaultdict(dict)
        self._streak_context: dict[str, str] = {}  # team -> "comp:season" key

    # ── Persistence helpers ───────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "extremes": {k: v.to_dict() for k, v in self.extremes.items()},
            "counters": dict(self.counters),
            "streaks": self.streaks,
            "comp_champions": dict(self.comp_champions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecordBook":
        book = cls()
        for key, entry in data.get("extremes", {}).items():
            book.extremes[key] = RecordHolder.from_dict(entry)
        for key, counts in data.get("counters", {}).items():
            book.counters[key] = dict(counts)
        book.streaks = data.get("streaks", {})
        book.comp_champions = defaultdict(
            dict, {k: dict(v) for k, v in data.get("comp_champions", {}).items()}
        )
        return book

    # ── Core update primitives ────────────────────────────────────────────────

    def _set_extreme(
        self,
        key: str,
        value: Any,
        holder: str,
        *,
        holder_id: str | None = None,
        higher_is_better: bool = True,
        team: str | None = None,
        season: str | None = None,
        competition: str | None = None,
        detail: str | None = None,
        secondary: str | None = None,
    ) -> bool:
        """Update if new value beats the current record. Returns True if updated."""
        current = self.extremes.get(key)
        if current is None:
            beats = True
        elif higher_is_better:
            beats = value > current.value
        else:
            beats = value < current.value

        if beats:
            self.extremes[key] = RecordHolder(
                value,
                holder,
                holder_id=holder_id,
                team=team,
                season=season,
                competition=competition,
                detail=detail,
                secondary=secondary,
            )
            return True
        return False

    def _increment_counter(
        self,
        key: str,
        entity_id: str,
        amount: int = 1,
        *,
        holder_name: str | None = None,
    ) -> int:
        counts = self.counters[key]
        counts[entity_id] = counts.get(entity_id, 0) + amount
        total = counts[entity_id]
        self._set_extreme(
            f"{key}:most",
            total,
            holder_name or entity_id,
            holder_id=entity_id,
            higher_is_better=True,
        )
        return total

    @staticmethod
    def _resolve_player(
        player_index,
        teams,
        *,
        player_id=None,
        name=None,
        team_name=None,
    ):
        if player_id and player_id in player_index:
            return player_index[player_id]
        player, tname = find_player(teams, player_id=player_id, name=name, team_name=team_name)
        return (player, tname) if player is not None else None

    @staticmethod
    def _players_in_match(
        result: dict, player_index: dict, teams
    ) -> list[tuple[Any, str]]:
        """All players who appeared (XI + subs from events)."""
        seen: set[str] = set()
        players = []

        def _add(pid: str | None, name: str | None, team_hint: str | None = None):
            if not pid and not name:
                return
            key = pid or name
            if key in seen:
                return
            resolved = RecordBook._resolve_player(
                player_index, teams, player_id=pid, name=name, team_name=team_hint
            )
            if resolved:
                seen.add(resolved[0].id)
                players.append(resolved)

        for side, team_hint in (("home_xi", result["home_team"]), ("away_xi", result["away_team"])):
            for entry in result.get(side, []):
                _add(entry.get("id"), entry.get("name"), team_hint)

        for evt in result.get("events", []):
            if evt["type"] == "substitution":
                _add(sub_on_id(evt), evt.get("player_on"), evt.get("team"))
                _add(sub_off_id(evt), evt.get("player_off"), evt.get("team"))

        return players

    # ── Per-match processing ──────────────────────────────────────────────────

    def process_match(
        self,
        result: dict,
        teams,
        *,
        competition_name: str,
        season_year: str,
        match_date: datetime.time,
    ) -> None:
        """Update records from a single completed match."""
        player_index = build_player_index(teams)
        comp_scope = _scope_comp(competition_name)
        all_scope = _scope_all()

        home = result["home_team"]
        away = result["away_team"]
        hg, ag = result["home_goals"], result["away_goals"]
        events = result.get("events", [])
        match_detail = f"{home} {hg}-{ag} {away} ({season_year})"

        # ── Match goal tallies per player ─────────────────────────────────────
        goals_by_id: dict[str, int] = defaultdict(int)
        for evt in events:
            if evt["type"] != "goal":
                continue
            pid = event_player_id(evt)
            if not pid:
                continue
            goals_by_id[pid] += 1

        for player_id, goals in goals_by_id.items():
            resolved = self._resolve_player(player_index, teams, player_id=player_id)
            if not resolved:
                continue
            player, team_name = resolved

            # Most goals in a single match
            for scope in (all_scope, _scope_team(team_name), comp_scope):
                self._set_extreme(
                    f"{scope}:player_most_goals_match",
                    goals,
                    player.name,
                    holder_id=player.id,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )

            # Braces and hat-tricks
            if goals >= 2:
                brace_key = f"{all_scope}:player_braces"
                self._increment_counter(
                    brace_key, player.id, holder_name=player.name
                )
                self._increment_counter(
                    f"{comp_scope}:player_braces", player.id, holder_name=player.name
                )
                self._increment_counter(
                    f"{_scope_team(team_name)}:player_braces",
                    player.id,
                    holder_name=player.name,
                )
            if goals >= 3:
                ht_key = f"{all_scope}:player_hattricks"
                self._increment_counter(ht_key, player.id, holder_name=player.name)
                self._increment_counter(
                    f"{comp_scope}:player_hattricks", player.id, holder_name=player.name
                )
                self._increment_counter(
                    f"{_scope_team(team_name)}:player_hattricks",
                    player.id,
                    holder_name=player.name,
                )

            # Youngest / oldest scorer
            age = player.age_on(match_date)
            for scope, rec_young, rec_old in (
                (all_scope, "player_youngest_scorer", "player_oldest_scorer"),
                (comp_scope, "player_youngest_scorer", "player_oldest_scorer"),
            ):
                self._set_extreme(
                    f"{scope}:{rec_young}",
                    age,
                    player.name,
                    holder_id=player.id,
                    higher_is_better=False,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )
                self._set_extreme(
                    f"{scope}:{rec_old}",
                    age,
                    player.name,
                    holder_id=player.id,
                    higher_is_better=True,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )

        # Fastest goal
        goal_events = [e for e in events if e["type"] == "goal"]
        if goal_events:
            fastest = min(goal_events, key=lambda e: e["minute"])
            team_name = fastest["team"]
            minute = fastest["minute"]
            scorer_resolved = self._resolve_player(
                player_index,
                teams,
                player_id=event_player_id(fastest),
                name=fastest.get("player"),
                team_name=team_name,
            )
            if scorer_resolved:
                scorer_player, _ = scorer_resolved
                scorer_label = scorer_player.name
                scorer_id = scorer_player.id
            else:
                scorer_label = fastest.get("player", "Unknown")
                scorer_id = event_player_id(fastest)
            detail = f"{scorer_label} {minute}' — {match_detail}"
            for scope in (all_scope, comp_scope, _scope_team(team_name)):
                self._set_extreme(
                    f"{scope}:player_fastest_goal",
                    minute,
                    scorer_label,
                    holder_id=scorer_id,
                    higher_is_better=False,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=detail,
                )

        # Most goals in one match (team total)
        total_goals = hg + ag
        for scope in (all_scope, comp_scope):
            self._set_extreme(
                f"{scope}:match_most_goals",
                total_goals,
                f"{home} vs {away}",
                season=season_year,
                competition=competition_name,
                detail=match_detail,
            )

        # Biggest win / loss (margin from each team's perspective)
        for team_name, gf, ga, opponent in (
            (home, hg, ag, away),
            (away, ag, hg, home),
        ):
            margin = gf - ga
            if margin > 0:
                self._set_extreme(
                    f"{_scope_team(team_name)}:team_biggest_win",
                    margin,
                    team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                    secondary=opponent,
                )
                self._set_extreme(
                    f"{comp_scope}:team_biggest_win",
                    margin,
                    team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )
            elif margin < 0:
                self._set_extreme(
                    f"{_scope_team(team_name)}:team_biggest_loss",
                    abs(margin),
                    team_name,
                    higher_is_better=True,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                    secondary=opponent,
                )

        # Home / away goals in competition (per team, per season running total)
        ha_key_home = f"{comp_scope}:season_home_goals:{season_year}:{home}"
        ha_key_away = f"{comp_scope}:season_away_goals:{season_year}:{away}"
        self.counters[ha_key_home][home] = self.counters[ha_key_home].get(home, 0) + hg
        self.counters[ha_key_away][away] = self.counters[ha_key_away].get(away, 0) + ag

        # Appearances / debuts — youngest & oldest to play
        for player, team_name in self._players_in_match(result, player_index, teams):
            age = player.age_on(match_date)
            for scope, rec_young, rec_old in (
                (all_scope, "player_youngest_debut", "player_oldest_debut"),
                (comp_scope, "player_youngest_debut", "player_oldest_debut"),
            ):
                self._set_extreme(
                    f"{scope}:{rec_young}",
                    age,
                    player.name,
                    holder_id=player.id,
                    higher_is_better=False,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )
                self._set_extreme(
                    f"{scope}:{rec_old}",
                    age,
                    player.name,
                    holder_id=player.id,
                    higher_is_better=True,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=match_detail,
                )

        # GK clean-sheet streak (starting GK only — matches simulation credit)
        self._update_gk_streaks(result, player_index, teams, season_year, competition_name)

        # Team streaks (wins, scoring, unbeaten) within competition season
        self._update_team_streaks(
            home, away, hg, ag, competition_name, season_year, comp_scope
        )

    def _update_gk_streaks(
        self,
        result: dict,
        player_index: dict,
        teams,
        season_year: str,
        competition_name: str,
    ) -> None:
        """Track consecutive clean-sheet matches for starting goalkeepers."""
        comp_scope = _scope_comp(competition_name)

        for side, conceded in (
            ("home", result["away_goals"]),
            ("away", result["home_goals"]),
        ):
            xi = result.get(f"{side}_xi", [])
            gk_entry = next((p for p in xi if p.get("position") == "GK"), None)
            if not gk_entry:
                continue
            team_hint = result["home_team"] if side == "home" else result["away_team"]
            resolved = self._resolve_player(
                player_index,
                teams,
                player_id=gk_entry.get("id"),
                name=gk_entry.get("name"),
                team_name=team_hint,
            )
            if not resolved:
                continue
            gk_player, team_name = resolved
            streak_key = f"gk_cs_streak:{comp_scope}:{season_year}:{gk_player.id}"

            if conceded == 0:
                self.counters[streak_key][gk_player.id] = (
                    self.counters[streak_key].get(gk_player.id, 0) + 1
                )
            else:
                self.counters[streak_key][gk_player.id] = 0

            streak = self.counters[streak_key].get(gk_player.id, 0)
            for scope in (_scope_all(), comp_scope, _scope_team(team_name)):
                self._set_extreme(
                    f"{scope}:gk_longest_clean_sheet_run",
                    streak,
                    gk_player.name,
                    holder_id=gk_player.id,
                    team=team_name,
                    season=season_year,
                    competition=competition_name,
                    detail=f"{streak} consecutive clean sheets",
                )

    def _update_team_streaks(
        self,
        home: str,
        away: str,
        hg: int,
        ag: int,
        competition_name: str,
        season_year: str,
        comp_scope: str,
    ) -> None:
        ctx = f"{comp_scope}:{season_year}"

        def outcome(gf, ga):
            if gf > ga:
                return "W"
            if gf < ga:
                return "L"
            return "D"

        for team, gf, ga in ((home, hg, ag), (away, ag, hg)):
            sk = f"streak:{ctx}:{team}"
            if sk not in self.streaks:
                self.streaks[sk] = {
                    "win": 0,
                    "scoring": 0,
                    "unbeaten": 0,
                }
            s = self.streaks[sk]
            o = outcome(gf, ga)

            # Winning run
            s["win"] = s["win"] + 1 if o == "W" else 0
            # Scoring run
            s["scoring"] = s["scoring"] + 1 if gf > 0 else 0
            # Unbeaten
            s["unbeaten"] = s["unbeaten"] + 1 if o in ("W", "D") else 0

            for metric, val in (
                ("team_longest_winning_run", s["win"]),
                ("team_longest_scoring_run", s["scoring"]),
                ("team_longest_unbeaten_run", s["unbeaten"]),
            ):
                for scope in (comp_scope, _scope_team(team)):
                    self._set_extreme(
                        f"{scope}:{metric}",
                        val,
                        team,
                        season=season_year,
                        competition=competition_name,
                    )
                self._set_extreme(
                    f"{_scope_all()}:{metric}",
                    val,
                    team,
                    season=season_year,
                    competition=competition_name,
                )

    # ── Season-end processing ─────────────────────────────────────────────────

    def finalize_season(self, comp, teams, season_year: str) -> None:
        """Process end-of-season standings and player aggregates."""
        competition_name = comp.name
        comp_scope = _scope_comp(competition_name)
        all_scope = _scope_all()

        sorted_table = sorted(
            comp.standings.items(),
            key=lambda x: (
                -x[1]["points"],
                -x[1]["goal_difference"],
                -x[1]["goals_for"],
                x[0],
            ),
        )

        if sorted_table:
            champion_name, champion_stats = sorted_table[0]
            # Consecutive competition titles
            prev = self.comp_champions[competition_name]
            for t in list(prev.keys()):
                if t != champion_name:
                    prev[t] = 0
            prev[champion_name] = prev.get(champion_name, 0) + 1
            streak = prev[champion_name]
            self._set_extreme(
                f"{comp_scope}:team_consecutive_titles",
                streak,
                champion_name,
                season=season_year,
                competition=competition_name,
                detail=f"{streak} consecutive titles",
            )

            # Point gap over runner-up (champion only)
            if len(sorted_table) >= 2:
                _, runner_stats = sorted_table[1]
                gap = champion_stats["points"] - runner_stats["points"]
                if gap > 0:
                    self._set_extreme(
                        f"{_scope_team(champion_name)}:team_max_point_gap_runner_up",
                        gap,
                        champion_name,
                        season=season_year,
                        competition=competition_name,
                        detail=f"{gap} pts clear ({season_year})",
                    )

        # Per-team season extremes from standings
        for pos, (team_name, stats) in enumerate(sorted_table, 1):
            team_scope = _scope_team(team_name)
            pts = stats["points"]
            season_tag = season_year

            pairs = [
                ("team_season_most_points", pts, True),
                ("team_season_least_points", pts, False),
                ("team_season_most_wins", stats["wins"], True),
                ("team_season_least_wins", stats["wins"], False),
                ("team_season_most_draws", stats["draws"], True),
                ("team_season_least_draws", stats["draws"], False),
                ("team_season_most_losses", stats["losses"], True),
                ("team_season_least_losses", stats["losses"], False),
                ("team_season_most_goals_for", stats["goals_for"], True),
                ("team_season_least_goals_for", stats["goals_for"], False),
                ("team_season_most_goals_against", stats["goals_against"], True),
                ("team_season_least_goals_against", stats["goals_against"], False),
                ("team_season_best_goal_difference", stats["goal_difference"], True),
                ("team_season_worst_goal_difference", stats["goal_difference"], False),
            ]
            for rec_type, value, higher in pairs:
                self._set_extreme(
                    f"{team_scope}:{rec_type}",
                    value,
                    team_name,
                    higher_is_better=higher,
                    season=season_tag,
                    competition=competition_name,
                )
                self._set_extreme(
                    f"{comp_scope}:{rec_type}",
                    value,
                    team_name,
                    higher_is_better=higher,
                    season=season_tag,
                    competition=competition_name,
                )

            # League position (1 = best)
            self._set_extreme(
                f"{team_scope}:team_best_league_position",
                pos,
                team_name,
                higher_is_better=False,
                season=season_tag,
                competition=competition_name,
            )
            self._set_extreme(
                f"{team_scope}:team_worst_league_position",
                pos,
                team_name,
                higher_is_better=True,
                season=season_tag,
                competition=competition_name,
            )

        # Home / away season totals → extremes
        for ha_label, ha_suffix in (("home", "season_home_goals"), ("away", "season_away_goals")):
            counter_prefix = f"{comp_scope}:{ha_suffix}:{season_year}"
            for key, totals in list(self.counters.items()):
                if not key.startswith(counter_prefix):
                    continue
                for team_name, total in totals.items():
                    rec = f"{comp_scope}:team_most_{ha_label}_goals_season"
                    self._set_extreme(
                        rec,
                        total,
                        team_name,
                        season=season_year,
                        competition=competition_name,
                    )

        # Player season & career leaderboards
        self._update_player_leaderboards(teams, season_year, competition_name)

        # GK season clean sheets & unbeaten start
        self._finalize_gk_records(teams, comp, season_year, competition_name)

        # Reset in-season streak counters for next season
        self._reset_season_streaks(comp_scope, season_year)

    def _reset_season_streaks(self, comp_scope: str, season_year: str) -> None:
        ctx = f"{comp_scope}:{season_year}"
        to_remove = [k for k in self.streaks if k.startswith(f"streak:{ctx}:")]
        for k in to_remove:
            del self.streaks[k]

    def _club_totals_for_player(self, player, club_name: str) -> tuple[int, int, int]:
        """Goals, assists, appearances while at club_name (history + current season)."""
        goals = assists = apps = 0
        for entry in player.career_history:
            if entry.get("team") == club_name:
                goals += entry.get("goals", 0)
                assists += entry.get("assists", 0)
                apps += entry.get("appearances", 0)
        # Current season not yet in history during finalize (called before end_season
        # in main — we'll add current in leaderboards separately)
        return goals, assists, apps

    def _update_player_leaderboards(
        self, teams, season_year: str, competition_name: str
    ) -> None:
        comp_scope = _scope_comp(competition_name)
        all_scope = _scope_all()

        for team in teams:
            team_scope = _scope_team(team.name)
            for player in team.squad:
                pname = player.name
                pid = player.id

                # Season totals (this competition is the only active one)
                for scope, goals, assists, apps, cs in (
                    (all_scope, player.goals, player.assists, player.appearances, player.clean_sheets),
                    (comp_scope, player.goals, player.assists, player.appearances, player.clean_sheets),
                    (team_scope, player.goals, player.assists, player.appearances, player.clean_sheets),
                ):
                    self._set_extreme(
                        f"{scope}:player_most_goals_season",
                        goals,
                        pname,
                        holder_id=pid,
                        team=team.name,
                        season=season_year,
                        competition=competition_name,
                    )
                    self._set_extreme(
                        f"{scope}:player_most_assists_season",
                        assists,
                        pname,
                        holder_id=pid,
                        team=team.name,
                        season=season_year,
                        competition=competition_name,
                    )
                    self._set_extreme(
                        f"{scope}:player_most_appearances_season",
                        apps,
                        pname,
                        holder_id=pid,
                        team=team.name,
                        season=season_year,
                        competition=competition_name,
                    )
                    if player.position == "GK":
                        self._set_extreme(
                            f"{scope}:gk_most_clean_sheets_season",
                            cs,
                            pname,
                            holder_id=pid,
                            team=team.name,
                            season=season_year,
                            competition=competition_name,
                        )

                # Career totals
                career_goals = player.career_goals + player.goals
                career_assists = player.career_assists + player.assists
                career_apps = player.career_appearances + player.appearances
                career_cs = player.career_clean_sheets + player.clean_sheets

                for scope, g, a, ap in (
                    (all_scope, career_goals, career_assists, career_apps),
                    (comp_scope, career_goals, career_assists, career_apps),
                ):
                    self._set_extreme(
                        f"{scope}:player_most_goals_career",
                        g,
                        pname,
                        holder_id=pid,
                        team=team.name,
                    )
                    self._set_extreme(
                        f"{scope}:player_most_assists_career",
                        a,
                        pname,
                        holder_id=pid,
                        team=team.name,
                    )
                    self._set_extreme(
                        f"{scope}:player_most_appearances_career",
                        ap,
                        pname,
                        holder_id=pid,
                        team=team.name,
                    )

                if player.position == "GK":
                    self._set_extreme(
                        f"{all_scope}:gk_most_clean_sheets_career",
                        career_cs,
                        pname,
                        holder_id=pid,
                        team=team.name,
                    )
                    self._set_extreme(
                        f"{comp_scope}:gk_most_clean_sheets_career",
                        career_cs,
                        pname,
                        holder_id=pid,
                        team=team.name,
                    )

                # Club all-time (player's current club)
                hist_g, hist_a, hist_ap = self._club_totals_for_player(player, team.name)
                club_goals = hist_g + player.goals
                club_assists = hist_a + player.assists
                club_apps = hist_ap + player.appearances

                self._set_extreme(
                    f"{team_scope}:player_club_goals",
                    club_goals,
                    pname,
                    holder_id=pid,
                    team=team.name,
                )
                self._set_extreme(
                    f"{team_scope}:player_club_assists",
                    club_assists,
                    pname,
                    holder_id=pid,
                    team=team.name,
                )
                self._set_extreme(
                    f"{team_scope}:player_club_appearances",
                    club_apps,
                    pname,
                    holder_id=pid,
                    team=team.name,
                )

    def _finalize_gk_records(
        self, teams, comp, season_year: str, competition_name: str
    ) -> None:
        """GK unbeaten start: longest initial unbeaten run in the season."""
        comp_scope = _scope_comp(competition_name)
        team_results: dict[str, list[tuple[str, int, int]]] = defaultdict(list)

        for r in comp.results:
            home, away = r["home_team"], r["away_team"]
            hg, ag = r["home_goals"], r["away_goals"]
            team_results[home].append(("home", hg, ag))
            team_results[away].append(("away", ag, hg))

        for team in teams:
            results = team_results.get(team.name, [])
            unbeaten_start = 0
            for _, gf, ga in results:
                if gf >= ga:
                    unbeaten_start += 1
                else:
                    break

            gks = [p for p in team.squad if p.position == "GK"]
            if not gks:
                continue
            # Credit team record to GK with most season clean sheets
            best_gk = max(gks, key=lambda p: p.clean_sheets)
            for scope in (_scope_all(), comp_scope, _scope_team(team.name)):
                self._set_extreme(
                    f"{scope}:gk_best_unbeaten_start",
                    unbeaten_start,
                    best_gk.name,
                    holder_id=best_gk.id,
                    team=team.name,
                    season=season_year,
                    competition=competition_name,
                    detail=f"{unbeaten_start} matches from season start",
                )

    # ── Display ───────────────────────────────────────────────────────────────

    RECORD_LABELS = {
        "player_most_goals_career": "Top career goal scorer",
        "player_most_assists_career": "Top career assister",
        "player_most_appearances_career": "Most career appearances",
        "player_most_goals_season": "Top season goal scorer",
        "player_most_assists_season": "Top season assister",
        "player_most_appearances_season": "Most season appearances",
        "player_most_goals_match": "Most goals in a match",
        "player_braces:most": "Most career braces",
        "player_hattricks:most": "Most career hat-tricks",
        "player_fastest_goal": "Fastest goal",
        "player_youngest_scorer": "Youngest goal scorer",
        "player_oldest_scorer": "Oldest goal scorer",
        "player_youngest_debut": "Youngest debutant",
        "player_oldest_debut": "Oldest debutant",
        "player_club_goals": "Most goals for club (all-time)",
        "player_club_assists": "Most assists for club (all-time)",
        "player_club_appearances": "Most appearances for club (all-time)",
        "team_biggest_win": "Biggest win (margin)",
        "team_biggest_loss": "Heaviest defeat (margin)",
        "team_season_most_points": "Most points in a season",
        "team_season_least_points": "Fewest points in a season",
        "team_season_best_league_position": "Best league finish",
        "team_season_worst_league_position": "Worst league finish",
        "team_max_point_gap_runner_up": "Largest title-winning margin (pts)",
        "team_longest_winning_run": "Longest winning run",
        "team_longest_scoring_run": "Longest scoring run",
        "team_longest_unbeaten_run": "Longest unbeaten run",
        "team_consecutive_titles": "Most consecutive competition titles",
        "match_most_goals": "Most goals in a match",
        "gk_most_clean_sheets_career": "Most career clean sheets (GK)",
        "gk_most_clean_sheets_season": "Most clean sheets in a season (GK)",
        "gk_longest_clean_sheet_run": "Longest clean-sheet run (matches, GK)",
        "gk_best_unbeaten_start": "Best unbeaten start to a season (GK/team)",
        "team_most_home_goals_season": "Most home goals in a season",
        "team_most_away_goals_season": "Most away goals in a season",
    }

    def get_record_label(self, record_suffix: str) -> str:
        return self.RECORD_LABELS.get(record_suffix, record_suffix.replace("_", " ").title())

    def print_records_summary(
        self,
        *,
        scopes: list[str] | None = None,
        season_year: str | None = None,
    ) -> None:
        """Print human-readable record summary for selected scopes."""
        if scopes is None:
            scopes = ["all"]

        print(f"\n{'='*80}")
        print("  CLUB & COMPETITION RECORDS")
        print(f"{'='*80}\n")

        shown = set()
        for key in sorted(self.extremes.keys()):
            scope, _, suffix = key.partition(":")
            if scope not in scopes and scopes != ["*"]:
                continue
            if suffix in shown:
                continue
            # Group comp-scoped under competition header once
            holder = self.extremes[key]
            if season_year and holder.season and holder.season != season_year:
                # Still show all-time; skip only season-tagged from other years for season section
                pass

            label = self.get_record_label(suffix)
            scope_label = scope.replace("comp:", "Competition: ").replace("team:", "Club: ")
            if scope == "all":
                scope_label = "All competitions"

            detail = f" — {holder.detail}" if holder.detail else ""
            team_part = f" ({holder.team})" if holder.team and holder.team != holder.holder else ""
            print(f"  [{scope_label}] {label}")
            print(f"    {holder.holder}{team_part}: {holder.value}{detail}")
            if holder.season:
                print(f"    Season: {holder.season}")
            print()
            shown.add(suffix)

    def print_season_records(self, comp, teams, season_year: str) -> None:
        """Print records set or tied this season."""
        comp_name = comp.name
        comp_scope = _scope_comp(comp_name)
        print(f"\n{'='*80}")
        print(f"  RECORDS & MILESTONES — {season_year} ({comp_name})")
        print(f"{'='*80}\n")

        self.print_records_summary(scopes=["all", comp_scope], season_year=season_year)

        print(f"  {'─'*76}")
        print("  Club records (all-time at current club)")
        print(f"  {'─'*76}\n")
        club_suffixes = (
            "player_club_goals",
            "player_club_assists",
            "player_club_appearances",
            "team_biggest_win",
            "team_biggest_loss",
        )
        for team in teams:
            team_scope = _scope_team(team.name)
            print(f"  {team.name}")
            for suffix in club_suffixes:
                key = f"{team_scope}:{suffix}"
                if key in self.extremes:
                    h = self.extremes[key]
                    label = self.get_record_label(suffix)
                    print(f"    {label}: {h.holder} ({h.value})")
            print()

        # Top 5 season scorers (live leaderboard, not just record holder)
        all_players = [(p, t.name) for t in teams for p in t.squad]
        scorers = sorted(all_players, key=lambda x: x[0].goals, reverse=True)[:5]
        if scorers and scorers[0][0].goals > 0:
            print("  Season top scorers:")
            for i, (p, tname) in enumerate(scorers, 1):
                print(f"    {i}. {p.name} ({tname}) — {p.goals} goals")
            print()
