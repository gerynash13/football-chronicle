"""
Stable player identity helpers.

Match events store player_id (canonical) and player (display name).
Legacy saves may only have player names; resolvers accept both.
"""

from __future__ import annotations

import uuid
from typing import Any


def new_player_id() -> str:
    return str(uuid.uuid4())


def new_team_id() -> str:
    """Generate a unique ID for a team."""
    return str(uuid.uuid4())


def new_competition_id() -> str:
    """Generate a unique ID for a competition."""
    return str(uuid.uuid4())


def player_ref(player) -> dict[str, str]:
    return {"player_id": player.id, "player": player.name}


def sub_refs(player_off, player_on) -> dict[str, str]:
    return {
        "player_off_id": player_off.id,
        "player_off": player_off.name,
        "player_on_id": player_on.id,
        "player_on": player_on.name,
    }


def goal_refs(scorer, assister=None) -> dict[str, Any]:
    refs = player_ref(scorer)
    if assister:
        refs["assister_id"] = assister.id
        refs["assister"] = assister.name
    else:
        refs["assister_id"] = None
        refs["assister"] = None
    return refs


def event_player_id(evt: dict) -> str | None:
    return evt.get("player_id")


def event_assister_id(evt: dict) -> str | None:
    return evt.get("assister_id")


def event_matches_id(evt: dict, player_id: str, name: str | None = None) -> bool:
    pid = evt.get("player_id")
    if pid:
        return pid == player_id
    return name is not None and evt.get("player") == name


def event_assister_matches_id(evt: dict, player_id: str, name: str | None = None) -> bool:
    aid = evt.get("assister_id")
    if aid:
        return aid == player_id
    return name is not None and evt.get("assister") == name


def event_player_matches(evt: dict, player) -> bool:
    pid = event_player_id(evt)
    if pid:
        return pid == player.id
    return evt.get("player") == player.name


def event_assister_matches(evt: dict, player) -> bool:
    aid = event_assister_id(evt)
    if aid:
        return aid == player.id
    return evt.get("assister") == player.name


def sub_on_id(evt: dict) -> str | None:
    return evt.get("player_on_id")


def sub_off_id(evt: dict) -> str | None:
    return evt.get("player_off_id")


def build_player_index(teams) -> dict[str, tuple[Any, str]]:
    """Map player id -> (Player, team_name)."""
    index: dict[str, tuple[Any, str]] = {}
    for team in teams:
        for player in team.squad:
            index[player.id] = (player, team.name)
    return index


def build_name_index(teams, team_name: str | None = None) -> dict[str, tuple[Any, str]]:
    """Fallback lookup by name; optional team_name disambiguates."""
    index: dict[str, tuple[Any, str]] = {}
    for team in teams:
        if team_name and team.name != team_name:
            continue
        for player in team.squad:
            index[player.name] = (player, team.name)
    return index


def find_player(
    teams,
    *,
    player_id: str | None = None,
    name: str | None = None,
    team_name: str | None = None,
):
    if player_id:
        for team in teams:
            for player in team.squad:
                if player.id == player_id:
                    return player, team.name
    if name:
        for team in teams:
            if team_name and team.name != team_name:
                continue
            for player in team.squad:
                if player.name == name:
                    return player, team.name
    return None, None


def xi_entry(player) -> dict:
    return {"id": player.id, "name": player.name, "position": player.position}


def name_from_xi(xi: list[dict], player_id: str) -> str | None:
    for entry in xi:
        if entry.get("id") == player_id:
            return entry.get("name")
    return None


def display_name(player_id: str, xi_lists: list[list[dict]], fallback: str | None = None) -> str:
    for xi in xi_lists:
        name = name_from_xi(xi, player_id)
        if name:
            return name
    return fallback or player_id[:8]
