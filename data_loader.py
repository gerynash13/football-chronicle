"""
data_loader.py — YAML config reader
 
Translates the static data files in data/ into typed Python objects
the rest of the codebase can use.
 
This module has one job: read files and return clean data.
It has no game logic, no runtime state, and no side effects.
 
PUBLIC FUNCTIONS
================
load_nations()       → dict[id, NationConfig]
load_teams()         → dict[id, TeamConfig]
load_competitions()  → dict[id, CompetitionConfig]
get_nation(id)       → NationConfig
get_team(id)         → TeamConfig
get_competition(id)  → CompetitionConfig
 
TIER DERIVATION
===============
Tier is never stored — it is always computed from prestige.
Use NationConfig.tier to get the current tier label for any prestige value.
 
Thresholds:
    0    – 1000  →  lower-tier
    1001 – 2500  →  low-tier
    2501 – 5000  →  mid-tier
    5001 – 7500  →  high-tier
    7501 – 10000 →  top-tier
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional
import yaml

# ── Path helpers ──────────────────────────────────────────────────────────────

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")

def _data_path(filename: str) -> str:
    return os.path.join(DATA_DIR, filename)

def _read_yaml(filename: str) -> list:
    path = _data_path(filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Data file not found: {path}\n"
            f"Make sure the data/ directory exists alongside your project root."
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []
    
# ── Tier thresholds ──────────────────────────────────────────────────────────

TIER_THRESHOLDS = [
    (7501, "top-tier"),
    (5001, "high-tier"),
    (2501, "mid-tier"),
    (1001, "low-tier"),
    (0, "lower-tier"),
]

# PA caps and wonderkid chances are derived from tiers
TIER_STATS = {
    "top-tier":     {"pa_cap": 180, "wonderkid_pa_cap": 200, "wonderkid_chance": 0.08},
    "high-tier":    {"pa_cap": 150, "wonderkid_pa_cap": 170, "wonderkid_chance": 0.06},
    "mid-tier":     {"pa_cap": 120, "wonderkid_pa_cap": 140, "wonderkid_chance": 0.05},
    "low-tier":     {"pa_cap": 85,  "wonderkid_pa_cap": 100, "wonderkid_chance": 0.04},
    "lower-tier":   {"pa_cap": 70,  "wonderkid_pa_cap": 82,  "wonderkid_chance": 0.02},
}

def prestige_to_tier(prestige: float) -> str:
    # Derive tier label from a prestige value
    for threshold, tier in TIER_THRESHOLDS:
        if prestige >= threshold:
            return tier
    return "lower-tier"

# ── Data classes ──────────────────────────────────────────────────────────────
#
# Why dataclasses instead of plain dicts?
# Dicts let you silently access a wrong key and get None.
# Dataclasses give you an AttributeError with the field name — much easier
# to debug. They also give you free __repr__ for printing during development.

@dataclass
class NationConfig:
    id:                         str
    name:                       str
    is_fictional:               bool
    founded_year:               int
    prestige:                   float
    prestige_weight_league:     float
    prestige_weight_cup:        float
    prestige_decay:             float
    prestige_floor:             float
    tier_change_min_seasons:    int
    name_generator:             str
    eligible_for_international: bool
    
    @property
    def tier(self) -> str:
        # Tier is always derived from current prestige, never stored
        return prestige_to_tier(self.prestige)
    
    @property
    def pa_cap(self) -> int:
        return TIER_STATS[self.tier]["pa_cap"]
    
    @property
    def wonderkid_pa_cap(self) -> int:
        return TIER_STATS[self.tier]["wonderkid_pa_cap"]
    
    @property
    def wonderkid_chance(self) -> float:
        return TIER_STATS[self.tier]["wonderkid_chance"]
    
    def to_player_config(self) -> dict:
        """
        Returns the dict shape that name_generator.py and player generation
        code expects — maintains backward compatibility with the old
        get_nation_config() interface.
        """
        return {
            "pa_cap": self.pa_cap,
            "wonderkid_pa_cap": self.wonderkid_pa_cap,
            "wonderkid_chance": self.wonderkid_chance,
        }
        
@dataclass
class TeamConfig:
    id:             str
    name:           str
    nation_id:      str
    founded_year:   int
    prestige:       float
    attack:         float
    midfield:       float
    defense:        float
    competitions:   list[str] = field(default_factory=list)
    
    @property
    def avg_ca(self) -> int:
        return (self.attack + self.midfield + self.defense) // 3
    
@dataclass
class CompetitionConfig:
    id:             str
    name:           str
    type:           str
    nation_id:      str
    founded_year:   int
    prestige:       float
    tier:           str
    frequency:      int
    timing:         str
    match_day:      str
    participants:   dict
    rounds:         list[int] = field(default_factory=list)
    
# ── Loaders ───────────────────────────────────────────────────────────────────

def load_nations() -> dict[str, NationConfig]:
    """
    Parse nations.yaml and return a dict keyed by nation id.
 
    Why return a dict instead of a list?
    The rest of the codebase looks up nations by id constantly.
    A dict gives O(1) lookup; a list would require O(n) search every time.
    """
    raw = _read_yaml("nations.yaml")
    result = {}
    for entry in raw:
        weights = entry.get("prestige_weights", {})
        result[entry["id"]] = NationConfig(
            id=entry["id"],
            name=entry["name"],
            is_fictional=entry.get("is_functional", False),
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 1000)),
            prestige_weight_league=float(weights.get("league", 0.60)),
            prestige_weight_cup=float(weights.get("cup", 0.40)),
            prestige_decay=float(entry.get("prestige_decay", 0.3)),
            prestige_floor=float(entry.get("prestige_floor", 500)),
            tier_change_min_seasons=int(entry.get("tier_change_min_seasons", 3)),
            name_generator=entry.get("name_generator", "myrian"),
            eligible_for_international=entry.get("eligible_for_international", True),
        )
    return result

def load_teams() -> dict[str, TeamConfig]:
    # Parse teams.yaml and return a dict keyed by team id
    raw = _read_yaml("teams.yaml")
    result = {}
    for entry in raw:
        result[entry["id"]] = TeamConfig(
            id=entry["id"],
            name=entry["name"],
            nation_id=entry["nation"],
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 1000)),
            attack=float(entry.get("attack", 50)),
            midfield=float(entry.get("midfield", 50)),
            defense=float(entry.get("defense", 50)),
            competitions=entry.get("competitions", []),
        )
    return result

def load_competitions() -> dict[str, CompetitionConfig]:
    # Parse competitions.yaml and return a dict keyed by competition id
    raw = _read_yaml("competitions.yaml")
    result = {}
    for entry in raw:
        result[entry["id"]] = CompetitionConfig(
            id=entry["id"],
            name=entry["name"],
            type=entry["type"],
            nation_id=entry["nation"],
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 1000)),
            tier=entry["tier"],
            frequency=int(entry.get("frequency", 1)),
            timing=entry.get("timing", "season"),
            match_day=entry.get("match_day", "primary"),
            participants=entry.get("participants", {}),
            rounds=entry.get("rounds", []),
        )
    return result

# ── Convenience accessors ─────────────────────────────────────────────────────
#
# These load and cache on first call. The cache is module-level, so the
# files are only read once per process — not once per function call.
# This pattern is called "lazy initialization".

_nations_cache:         dict[str, NationConfig] = {}
_teams_cache:           dict[str, TeamConfig] = {}
_competitions_cache:    dict[str, CompetitionConfig] = {}

def get_nation(nation_id: str) -> NationConfig:
    global _nations_cache
    if not _nations_cache:
        _nations_cache = load_nations()
    if team_id not in _teams_cache:
        raise ValueError(f"Nation '{nation_id}' not found in nations.yaml.")
    return _nations_cache[nation_id]

def get_team(team_id: str) -> TeamConfig:
    global _teams_cache
    if not _teams_cache:
        _teams_cache = load_teams()
    if team_id not in _teams_cache:
        raise ValueError(f"Team '{team_id}' not found in teams.yaml.")
    return _teams_cache[team_id]

def get_competition(competition_id: str) -> CompetitionConfig:
    global _competitions_cache
    if not _competitions_cache:
        _competitions_cache = load_competitions()
    if competition_id not in _competitions_cache:
        raise ValueError(f"Competition '{competition_id}' not found in competitions.yaml.")
    return _competitions_cache[competition_id]

def teams_for_season(season_year: str) -> list[TeamConfig]:
    """
    Return all teams whose founded_year is <= the start year of this season.
    This is the filter that makes team founding years work automatically.
    """
    start_year = int(season_year.split("/")[0])
    all_teams = load_teams()
    return [team for team in all_teams.values() if team.founded_year <= start_year]

def competitions_for_season(season_year: str) -> list[CompetitionConfig]:
    """
    Return all competitions that exist in this season year, respecting
    founded_year and frequency (e.g. Olympics only runs every 4 years).
    """
    start_year = int(season_year.split("/")[0])
    all_comps = load_competitions()
    result = []
    for comp in all_comps.values():
        if comp.founded_year > start_year:
            continue
        # For frequency > 1, only include if (year - founded year) % frequency == 0
        years_since = start_year - comp.founded_year
        if comp.frequency > 1 and years_since % comp.frequency != 0:
            continue
        result.append(comp)
    return result

def teams_in_competition(comp_id: str, season_year: str) -> list[TeamConfig]:
    """
    Return all teams that are members of a competition in a given season,
    filtering by founding year.
    """
    start_year = int(season_year.split("/")[0])
    all_teams = load_teams()
    return [
        team for team in all_teams.values() 
        if team in team.competitions
        and team.founded_year <= start_year
    ]