from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from data_loader import Journalist

SCOPE_ORDER = ["local", "regional", "national", "continental", "global"]

def _scope_rank(scope: str) -> int:
    return SCOPE_ORDER.index(scope)

@dataclass
class Article:
    journalist_id: str
    headline: str
    body: str
    date: str
    season: str
    event_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    teams: list = field(default_factory=list)
    players: list = field(default_factory=list)
    
COMPREHENSIVE_TIERS = {"local", "regional", "national"}

EVENT_MAGNITUDE = {
    "match_result":         "national",
    "hat_trick":            "national",
    "goal_milestone":       "national",
    "injury_update":        "local",
    "promotion":            "national",
    "relegation":           "national",
    "manager_sacked":       "national",
    "transfer_completed":   "national",
    "wonderkid_emerges":    "national",
    "competition_winner":   "continental",
    "record_broken":        "global",
}

def _event_magnitude(event: dict) -> str:
    """How big a story this inherently is, independent of whose patch it's in."""
    return EVENT_MAGNITUDE.get(event["type"], "local")

def _involves_team(event: dict, team_name: str) -> bool:
    return team_name in (
        event.get("home_team"), event.get("away_team"),
        event.get("team"), event.get("winner")
    )
    
def _team_nation(teams: list, team_name: str | None) -> str | None:
    if not team_name:
        return None
    team = next((t for t in teams if t.name == team_name), None)
    return team.nation_id if team else None

def _in_jurisdiction(journalist: Journalist, event: dict, teams: list) -> bool:
    """Whether this event falls inside the patch this journalist comprehensively covers."""
    if journalist.favorite_team and _involves_team(event, journalist.favorite_team):
        return True
    if journalist.tier == "national" and journalist.nation_id:
        for key in ("home_team", "away_team", "team", "winner"):
            if _team_nation(teams, event.get(key)) == journalist.nation_id:
                return True
    return False

def covers_event(journalist: Journalist, event: dict, teams: list) -> bool:
    """
    Narrow-patch tiers (local/regional/national) cover their own patch
    unconditionally, regardless of how routine the story is — that's
    their whole beat. Everyone else only crosses in (or covers their
    own nominal "patch", for continental/global, which is too broad to
    be comprehensive about) if the story is big enough to matter
    worldwide.
    """
    if journalist.tier in COMPREHENSIVE_TIERS and _in_jurisdiction(journalist, event, teams):
        return True
    return _event_magnitude(event) == "global"