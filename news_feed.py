"""
news_feed.py — News Feed Foundation

The NewsFeed captures structured events as they happen in the game world.
It is the event capture layer only — it stores raw events.
The news generator (built later) reads these events and writes articles.
Journalist personalities, source tiers, and filtering all come later too.

This file must stay stable because the engine, simulation, and competition
layers all publish into it. Changing the publish() interface later would
require touching every callsite.

PUBLIC INTERFACE
================
feed = NewsFeed()
feed.publish(event_dict)           # add an event
feed.get_events(since=date)        # retrieve events since a date
feed.get_events(relevance="local") # retrieve by relevance tier
feed.clear_before(date)            # prune old events to control memory

EVENT SCHEMA
============
Every event dict must have at minimum:

    type:        str   — what happened (see EVENT TYPES below)
    date:        str   — ISO date string
    relevance:   list  — one or more of: "global", "regional", "local"
    season:      str   — season label e.g. "1896/97"

Additional fields depend on the event type.

EVENT TYPES
===========
match_result        — a match finished
    competition:    str
    home_team:      str
    away_team:      str
    home_goals:     int
    away_goals:     int
    home_region:    str   (for regional filtering)
    away_region:    str

goal_milestone      — a player reached a career goals milestone
    player:         str
    player_id:      str
    team:           str
    milestone:      int   (e.g. 50, 100, 200)
    competition:    str

hat_trick           — a player scored 3+ goals in one match
    player:         str
    player_id:      str
    team:           str
    goals:          int
    competition:    str
    match:          str   (e.g. "Team A 4-1 Team B")

record_broken       — an all-time record was set
    record_type:    str   (e.g. "most_goals_season")
    holder:         str
    value:          int or float
    previous_value: int or float
    competition:    str

competition_winner  — a competition was won
    competition:    str
    winner:         str
    runner_up:      str   (or null)
    season:         str

promotion           — a team was promoted (future use)
relegation          — a team was relegated (future use)
manager_sacked      — a manager was dismissed (future use)
transfer_completed  — a transfer was finalised (future use)
wonderkid_emerges   — a young player had a breakout performance (future use)
injury_update       — a significant injury (future use)

RELEVANCE TIERS
===============
global   — shown to all users regardless of their club or region
           Reserved for events with worldwide significance:
           champions league winner, world cup winner, all-time record broken,
           exceptionally high prestige match results

regional — shown to users whose club is in the same geographic region
           as one of the teams involved

local    — shown to users in the same league, or whose club is a rival
           or recent opponent of the teams involved

A single event can carry multiple relevance tags.
e.g. a hat-trick in the Champions League final might be:
    relevance: ["global", "regional", "local"]
"""

from __future__ import annotations

import datetime
from collections import deque
from typing import Any


class NewsFeed:

    def __init__(self, max_events: int = 2000):
        """
        max_events caps memory usage during long simulations.
        Oldest events are dropped first when the limit is reached.
        2000 is roughly two full seasons of events.
        """
        self._events: deque[dict] = deque(maxlen=max_events)

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, event: dict) -> None:
        """
        Add an event to the feed.

        The event dict is stored as-is. Callers are responsible for
        including all required fields (type, date, relevance, season).
        Missing fields will not raise errors here — they'll surface when
        the news generator tries to render the event later.

        Why not validate here?
        Validation at publish time would couple this class to the event
        schema, making it harder to add new event types. Loose coupling
        is more valuable than early error detection for this layer.
        """
        self._events.append(event)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def get_events(
        self,
        *,
        since: datetime.date | None = None,
        until: datetime.date | None = None,
        relevance: str | None = None,
        event_type: str | None = None,
        team: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Retrieve events matching the given filters.

        All filters are optional and combinable.
        Results are returned in chronological order (oldest first).

        since / until   — filter by date range (inclusive)
        relevance       — "global" | "regional" | "local"
        event_type      — match against the "type" field
        team            — match against any team field in the event
        limit           — return at most this many events (most recent)
        """
        results = []
        for evt in self._events:
            if since:
                evt_date = self._parse_date(evt.get("date"))
                if evt_date and evt_date < since:
                    continue
            if until:
                evt_date = self._parse_date(evt.get("date"))
                if evt_date and evt_date > until:
                    continue
            if relevance and relevance not in evt.get("relevance", []):
                continue
            if event_type and evt.get("type") != event_type:
                continue
            if team:
                # Check any field that might contain a team name
                found = (
                    evt.get("team") == team
                    or evt.get("home_team") == team
                    or evt.get("away_team") == team
                    or evt.get("winner") == team
                )
                if not found:
                    continue
            results.append(evt)

        if limit:
            results = results[-limit:]
        return results

    def get_recent(self, n: int = 20) -> list[dict]:
        """Return the n most recent events regardless of type."""
        events = list(self._events)
        return events[-n:]

    # ── Maintenance ───────────────────────────────────────────────────────────

    def clear_before(self, cutoff_date: datetime.date) -> int:
        """
        Remove all events older than cutoff_date.
        Returns the number of events removed.
        """
        before = len(self._events)
        self._events = deque(
            (e for e in self._events
             if self._parse_date(e.get("date"), default=cutoff_date) >= cutoff_date),
            maxlen=self._events.maxlen,
        )
        return before - len(self._events)

    def __len__(self) -> int:
        return len(self._events)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_date(
        value: Any,
        default: datetime.date | None = None
    ) -> datetime.date | None:
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            try:
                return datetime.date.fromisoformat(value)
            except ValueError:
                pass
        return default


# ── Convenience publisher functions ──────────────────────────────────────────
#
# These are thin wrappers that build correctly-shaped event dicts.
# Using functions instead of building dicts inline at every callsite means:
#   1. The schema is defined in one place
#   2. Callsites are readable
#   3. Adding a new required field means changing one function, not 20 callsites

def publish_match_result(
    feed: NewsFeed,
    *,
    competition: str,
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
    date: datetime.date,
    season: str,
    home_region: str = "",
    away_region: str = "",
    relevance: list[str] | None = None,
) -> None:
    if relevance is None:
        relevance = ["local"]
    feed.publish({
        "type":        "match_result",
        "date":        date.isoformat(),
        "season":      season,
        "relevance":   relevance,
        "competition": competition,
        "home_team":   home_team,
        "away_team":   away_team,
        "home_goals":  home_goals,
        "away_goals":  away_goals,
        "home_region": home_region,
        "away_region": away_region,
    })


def publish_hat_trick(
    feed: NewsFeed,
    *,
    player: str,
    player_id: str,
    team: str,
    goals: int,
    competition: str,
    match: str,
    date: datetime.date,
    season: str,
    relevance: list[str] | None = None,
) -> None:
    if relevance is None:
        relevance = ["local", "regional"]
    feed.publish({
        "type":        "hat_trick",
        "date":        date.isoformat(),
        "season":      season,
        "relevance":   relevance,
        "player":      player,
        "player_id":   player_id,
        "team":        team,
        "goals":       goals,
        "competition": competition,
        "match":       match,
    })


def publish_competition_winner(
    feed: NewsFeed,
    *,
    competition: str,
    winner: str,
    runner_up: str | None,
    date: datetime.date,
    season: str,
    relevance: list[str] | None = None,
) -> None:
    if relevance is None:
        relevance = ["regional"]
    feed.publish({
        "type":        "competition_winner",
        "date":        date.isoformat(),
        "season":      season,
        "relevance":   relevance,
        "competition": competition,
        "winner":      winner,
        "runner_up":   runner_up,
    })


def publish_record_broken(
    feed: NewsFeed,
    *,
    record_type: str,
    holder: str,
    value: Any,
    previous_value: Any,
    competition: str,
    date: datetime.date,
    season: str,
    relevance: list[str] | None = None,
) -> None:
    if relevance is None:
        relevance = ["global"]
    feed.publish({
        "type":           "record_broken",
        "date":           date.isoformat(),
        "season":         season,
        "relevance":      relevance,
        "record_type":    record_type,
        "holder":         holder,
        "value":          value,
        "previous_value": previous_value,
        "competition":    competition,
    })