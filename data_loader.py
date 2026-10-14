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
            f"Make sure the data/ directory exists alongside your project files."
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


# ── Tier thresholds ───────────────────────────────────────────────────────────

TIER_THRESHOLDS = [
    (7501, "top-tier"),
    (5001, "high-tier"),
    (2501, "mid-tier"),
    (1001, "low-tier"),
    (0,    "lower-tier"),
]

# PA caps and wonderkid chances derived from tier
# These replace the hardcoded TIER_DEFAULTS in the old nations.py
TIER_STATS = {
    "top-tier":   {"pa_cap": 180, "wonderkid_pa_cap": 200, "wonderkid_chance": 0.08},
    "high-tier":  {"pa_cap": 150, "wonderkid_pa_cap": 170, "wonderkid_chance": 0.06},
    "mid-tier":   {"pa_cap": 120, "wonderkid_pa_cap": 140, "wonderkid_chance": 0.05},
    "low-tier":   {"pa_cap": 85,  "wonderkid_pa_cap": 100, "wonderkid_chance": 0.04},
    "lower-tier": {"pa_cap": 70,  "wonderkid_pa_cap": 82,  "wonderkid_chance": 0.02},
}


def prestige_to_tier(prestige: float) -> str:
    """Derive tier label from a prestige value."""
    for threshold, label in TIER_THRESHOLDS:
        if prestige >= threshold:
            return label
    return "lower-tier"


# ── Data classes ──────────────────────────────────────────────────────────────
#
# Why dataclasses instead of plain dicts?
# Dicts let you silently access a wrong key and get None.
# Dataclasses give you an AttributeError with the field name — much easier
# to debug. They also give you free __repr__ for printing during development.

@dataclass
class RegionConfig:
    id:               str
    name:             str
    nation_id:        str   # set when loading, so regions know their parent
    talent_modifier:  float = 1.0


@dataclass
class NationConfig:
    id:                      str
    name:                    str
    is_fictional:            bool
    founded_year:            int
    prestige:                float
    prestige_weight_league:  float
    prestige_weight_intl:    float
    prestige_decay:          float
    prestige_floor:          float
    tier_change_min_seasons: int
    name_generator:          str
    eligible_for_international: bool
    regions:                 list = field(default_factory=list)  # list[RegionConfig]

    @property
    def tier(self) -> str:
        """Tier is always derived from current prestige, never stored."""
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
            "pa_cap":          self.pa_cap,
            "wonderkid_pa_cap": self.wonderkid_pa_cap,
            "wonderkid_chance": self.wonderkid_chance,
        }


@dataclass
class TeamConfig:
    id:                     str
    name:                   str
    nation_id:              str
    league_nation_id:       Optional[str]
    home_region:            str
    founded_year:           int
    prestige:               float
    attack:                 int
    midfield:               int
    defense:                int
    budget:                 int
    wage_budget:            int
    competitions:           list[str] = field(default_factory=list)
    league_nation_id_year:  Optional[int] = None

    @property
    def avg_ca(self) -> int:
        return (self.attack + self.midfield + self.defense) // 3


@dataclass
class CompetitionConfig:
    id:           str
    name:         str
    type:         str           # league | cup | supercup | international_*
    nation_id:    Optional[str] # null for international competitions
    founded_year: int
    prestige:     float
    tier:         Optional[int]
    frequency:    int
    timing:       str           # season | end_of_season | summer
    match_day:    str           # primary | midweek | flexible
    participants: dict
    rounds:       list[int] = field(default_factory=list)
    # draw_rules: how a draw is resolved in single-elimination / supercup matches
    # Keys: extra_time (bool), penalties (bool), replay (bool)
    # Absent for league competitions - defaults to empty dict
    draw_rules:   dict = field(default_factory=dict)
    # legs: 1 for single match, 2 for home-and-away (two-leg logic not yet wired)
    legs:         int = 1
    
@dataclass
class Journalist:
    id:                    str
    name:                  str
    tier:                  str            # global | continental | national | regional | local
    style:                 str            # investigative | analytical | gossip | opinionated | dramatic
    reliability:           float          # 0.0-1.0 - lower leans toward spun tone
    favorite_team:         Optional[str] = None # team *name*, biases coverage toward that team
    active_from:           Optional[int] = None # year journalist started covering football. None means always active.
    nation_id:             Optional[str] = None # home nation - jurisdiction anchor for tier="national"

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_nations() -> dict[str, NationConfig]:
    raw = _read_yaml("nations.yaml")
    result = {}
    for entry in raw:
        weights = entry.get("prestige_weights", {})

        raw_regions = entry.get("regions", [])
        regions = [
            RegionConfig(
                id=r["id"],
                name=r["name"],
                nation_id=entry["id"],
                talent_modifier=float(r.get("talent_modifier", 1.0)),
            )
            for r in raw_regions
        ]

        result[entry["id"]] = NationConfig(
            id=entry["id"],
            name=entry["name"],
            is_fictional=entry.get("is_fictional", False),
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 1000)),
            prestige_weight_league=float(weights.get("league", 0.60)),
            prestige_weight_intl=float(weights.get("international", 0.40)),
            prestige_decay=float(entry.get("prestige_decay", 0.03)),
            prestige_floor=float(entry.get("prestige_floor", 500)),
            tier_change_min_seasons=int(entry.get("tier_change_min_seasons", 3)),
            name_generator=entry.get("name_generator", "myrian"),
            eligible_for_international=entry.get("eligible_for_international", True),
            regions=regions,
        )
    return result


def load_teams() -> dict[str, TeamConfig]:
    """Parse teams.yaml and return a dict keyed by team id."""
    raw = _read_yaml("teams.yaml")
    result = {}
    for entry in raw:
        result[entry["id"]] = TeamConfig(
            id=entry["id"],
            name=entry["name"],
            nation_id=entry["nation_id"],
            league_nation_id=entry.get("league_nation_id"),
            league_nation_id_year=entry.get("league_nation_id_year"),
            home_region=entry.get("home_region", ""),
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 500)),
            attack=int(entry.get("attack", 50)),
            midfield=int(entry.get("midfield", 50)),
            defense=int(entry.get("defense", 50)),
            budget=int(entry.get("budget", 1000)),
            wage_budget=int(entry.get("wage_budget", 300)),
            competitions=entry.get("competitions", []),
        )
    return result


def load_competitions() -> dict[str, CompetitionConfig]:
    """Parse competitions.yaml and return a dict keyed by competition id."""
    raw = _read_yaml("competitions.yaml")
    result = {}
    for entry in raw:
        result[entry["id"]] = CompetitionConfig(
            id=entry["id"],
            name=entry["name"],
            type=entry["type"],
            nation_id=entry.get("nation_id"),
            founded_year=entry.get("founded_year", 0),
            prestige=float(entry.get("prestige", 1000)),
            tier=entry.get("tier"),
            frequency=int(entry.get("frequency", 1)),
            timing=entry.get("timing", "season"),
            match_day=entry.get("match_day", "primary"),
            participants=entry.get("participants", {}),
            rounds=entry.get("rounds", []),
            draw_rules=entry.get("draw_rules", {}),
            legs=entry.get("legs", 1),
        )
    return result

def load_journalists() -> dict[str, Journalist]:
    """Parse journalists.yaml and return a dict keyed by journalist id."""
    raw = _read_yaml("journalists.yaml")
    result = {}
    for entry in raw:
        result[entry["id"]] = Journalist(
            id=entry["id"],
            name=entry["name"],
            tier=entry["tier"],
            style=entry["style"],
            reliability=float(entry.get("reliability", 0.7)),
            favorite_team=entry.get("favorite_team"),
            active_from=entry.get("active_from"),
            nation_id=entry.get("nation_id")
        )
    return result


# ── Convenience accessors ─────────────────────────────────────────────────────
#
# These load and cache on first call. The cache is module-level, so the
# files are only read once per process — not once per function call.
# This pattern is called "lazy initialisation".

_nations_cache:      dict[str, NationConfig]      = {}
_teams_cache:        dict[str, TeamConfig]         = {}
_competitions_cache: dict[str, CompetitionConfig] = {}
_journalists_cache:  dict[str, Journalist]        = {}


def get_nation(nation_id: str) -> NationConfig:
    global _nations_cache
    if not _nations_cache:
        _nations_cache = load_nations()
    if nation_id not in _nations_cache:
        raise ValueError(f"Nation '{nation_id}' not found in nations.yaml")
    return _nations_cache[nation_id]


def get_team(team_id: str) -> TeamConfig:
    global _teams_cache
    if not _teams_cache:
        _teams_cache = load_teams()
    if team_id not in _teams_cache:
        raise ValueError(f"Team '{team_id}' not found in teams.yaml")
    return _teams_cache[team_id]


def get_region(region_id: str) -> RegionConfig:
    """Find a region by id across all nations."""
    global _nations_cache
    if not _nations_cache:
        _nations_cache = load_nations()
    for nation in _nations_cache.values():
        for region in nation.regions:
            if region.id == region_id:
                return region
    raise ValueError(f"Region '{region_id}' not found in any nation in nations.yaml")

def get_competition(comp_id: str) -> CompetitionConfig:
    global _competitions_cache
    if not _competitions_cache:
        _competitions_cache = load_competitions()
    if comp_id not in _competitions_cache:
        raise ValueError(f"Competition '{comp_id}' not found in competitions.yaml")
    return _competitions_cache[comp_id]

def get_journalist(journalist_id: str) -> Journalist:
    global _journalists_cache
    if not _journalists_cache:
        _journalists_cache = load_journalists()
    if journalist_id not in _journalists_cache:
        raise ValueError(f"Journalist '{journalist_id}' not found in journalists.yaml")
    return _journalists_cache[journalist_id]


def teams_for_season(season_year: str) -> list[TeamConfig]:
    """
    Return all teams whose founded_year is <= the start year of this season.
    This is the filter that makes team founding years work automatically.
    """
    start_year = int(season_year.split("/")[0])
    all_teams  = load_teams()
    return [t for t in all_teams.values() if t.founded_year <= start_year]


def competitions_for_season(season_year: str) -> list[CompetitionConfig]:
    """
    Return all competitions that exist in this season year, respecting
    founded_year and frequency (e.g. Olympics only runs every 4 years).
    """
    start_year   = int(season_year.split("/")[0])
    all_comps    = load_competitions()
    result       = []
    for comp in all_comps.values():
        if comp.founded_year > start_year:
            continue
        # For frequency > 1, only include if (year - founded_year) % frequency == 0
        years_since = start_year - comp.founded_year
        if comp.frequency > 1 and years_since % comp.frequency != 0:
            continue
        result.append(comp)
    return result

def journalists_for_season(season_year: str) -> list[Journalist]:
    """
    Return all journalists that are active in this season year, respecting
    active_from (e.g. a journalist may not have started covering football yet).
    """
    start_year   = int(season_year.split("/")[0])
    all_journalists = load_journalists()
    result       = [
        j for j in all_journalists.values()
        if j.active_from is None or j.active_from <= start_year
    ]
    return result


def teams_in_competition(comp_id: str, season_year: str) -> list[TeamConfig]:
    """
    Return all teams that are members of a competition in a given season,
    filtering by founding year.
    """
    start_year = int(season_year.split("/")[0])
    all_teams  = load_teams()
    return [
        t for t in all_teams.values()
        if comp_id in t.competitions
        and t.founded_year <= start_year
    ]