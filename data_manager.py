import json
import datetime
from rng import rng
try:
    from classes import Team, Player
except ModuleNotFoundError:
    from team import Team
    from player import Player
from records import RecordBook
from player_refs import new_player_id
import copy
from facilities import DEFAULT_FACILITIES

# one list of (field, default) drives BOTH saving and loading
_PLAYER_DEFAULTS = {
    "is_retired": False, "retired_season": None, "morale": 0.0,
    "manager_relationship": 0.0, "squad_number": None, "is_wonderkid": False,
    "goals": 0, "assists": 0, "appearances": 0, "clean_sheets": 0,
    "season_avg_rating": 0.0, "season_rating_appearances": 0,
    "yellow_cards_by_comp": {}, "red_cards": 0,
    "is_suspended": False, "suspension_matches_left": 0,
    "is_injured": False, "injury_matches_left": 0, "injury_severity": None,
    "career_goals": 0, "career_assists": 0, "career_appearances": 0,
    "career_clean_sheets": 0, "career_yellow_cards": 0, "career_red_cards": 0,
    "career_injuries": 0, "career_trophies": 0, "career_trophies_by_comp": {},
    "career_history": [],
}


def player_to_dict(player):
    data = {
        "id": player.id, "name": player.name, "position": player.position,
        "birth_date": player.birth_date.isoformat(),
        "current_ability": player.current_ability,
        "potential_ability": player.potential_ability,
        "nationality": player.nationality,
        "parent_nationality": player.parent_nationality,
        "birth_region": player.birth_region, "preferred_foot": player.preferred_foot,
        "contract_expires": player.contract_expires, "wage": player.wage,
        "personality": player.personality, "attributes": player.attributes,
        "role": player.role,
    }
    for key in _PLAYER_DEFAULTS:
        data[key] = getattr(player, key)
        data["injury_until"] = player.injury_until.isoformat() if player.injury_until else None
    return data


def player_from_dict(d):
    player = Player(
        name=d["name"], position=d["position"],
        birth_date=datetime.date.fromisoformat(d["birth_date"]),
        current_ability=d["current_ability"], potential_ability=d["potential_ability"],
        player_id=d.get("id") or new_player_id(),
        nationality=d.get("nationality"), parent_nationality=d.get("parent_nationality"),
        birth_region=d.get("birth_region"), preferred_foot=d.get("preferred_foot"),
        contract_expires=d.get("contract_expires"), wage=d.get("wage", 0),
    )
    for key in ("personality", "attributes", "role"):
        if d.get(key):
            setattr(player, key, d[key])
    for key, default in _PLAYER_DEFAULTS.items():
        setattr(player, key, d.get(key, copy.deepcopy(default)))
    raw = d.get("injury_until")
    player.injury_until = datetime.date.fromisoformat(raw) if raw else None
    return player


def save_teams_to_file(teams, filename="teams_data.json"):
    data = [{
        "id": t.id, "name": t.name, "nation_id": t.nation_id,
        "league_nation_id": t.league_nation_id,
        "league_nation_id_year": t.league_nation_id_year,
        "attack": t.attack, "midfield": t.midfield, "defense": t.defense,
        "morale": t.morale, "board_confidence": t.board_confidence,
        "fan_satisfaction": t.fan_satisfaction, "prestige": t.prestige,
        "home_region": t.home_region, "budget": t.budget, "wage_budget": t.wage_budget,
        "trophies": t.trophies, "squad":   [player_to_dict(p) for p in t.squad],
        "retired": [player_to_dict(p) for p in t.retired], "facilities": t.facilities,
        "youth": [player_to_dict(p) for p in t.youth], "released": [player_to_dict(p) for p in t.released],
        "competitions": t.competitions
    } for t in teams]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(teams)} teams to {filename}")


def load_teams_from_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    teams = []
    for td in data:
        team = Team(name=td["name"], attack=td["attack"],
                    midfield=td["midfield"], defense=td["defense"])
        team.id                    = td.get("id") or team.id
        team.nation_id             = td.get("nation_id", "")
        team.league_nation_id      = td.get("league_nation_id", "")
        team.league_nation_id_year = td.get("league_nation_id_year")
        team.morale                = td.get("morale", 0.0)
        team.board_confidence      = td.get("board_confidence", 50.0)
        team.fan_satisfaction      = td.get("fan_satisfaction", 50.0)
        team.prestige              = td.get("prestige", 500.0)
        team.home_region           = td.get("home_region", "")
        team.budget                = td.get("budget", 1000)
        team.wage_budget           = td.get("wage_budget", 300)
        team.trophies              = td.get("trophies", [])
        team.squad   = [player_from_dict(d) for d in td.get("squad", [])]
        team.retired = [player_from_dict(d) for d in td.get("retired", [])]
        team.facilities = {**DEFAULT_FACILITIES, **td.get("facilities", {})}
        team.youth = [player_from_dict(d) for d in td.get("youth", [])]
        team.released = [player_from_dict(d) for d in td.get("released", [])]
        team.competitions = td.get("competitions", [])
        teams.append(team)
    return teams

def save_competition_to_file(competition, current_date, filename="competition_data.json"):
    """Save competition to resume later"""
    
    def _team_name(val):
        # Accept either a Team object or a plain string
        return val.name if hasattr(val, "name") else val
    
    # Convert results to JSON-friendly format
    serializable_results = []
    for result in competition.results:
        serializable_results.append({
            "home_team":    _team_name(result["home_team"]),
            "away_team":    _team_name(result["away_team"]),
            "home_goals":   result["home_goals"],
            "away_goals":   result["away_goals"],
            "events":       result.get("events", []),
            "matchday":     result.get("matchday")
        })
        
    comp_data = {
        "name":                 competition.name,
        "type":                 competition.type,
        "current_matchday":     competition.current_matchday,
        "standings":            competition.standings,
        "results":              serializable_results,
        "completed_matchdays":  list(competition.completed_matchdays),
        "current_date":         current_date.isoformat()
    }
        
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(comp_data, f, indent=2, ensure_ascii=False)

    print(f"Saved competition to {filename}")
    
    
def load_competition_data(competition, filename="competition_data.json"):
    """Load saved competition state into a competition object"""
    with open(filename, "r", encoding="utf-8") as f:
        comp_data = json.load(f)
        
    competition.current_matchday    = comp_data["current_matchday"]
    competition.standings           = comp_data["standings"]
    competition.results             = comp_data["results"]
    competition.completed_matchdays = set(comp_data.get("completed_matchdays", []))
    
    current_date = datetime.date.fromisoformat(
        comp_data.get("current_date", datetime.date.today().isoformat())
    )
    
    print(f"Loaded competition state from {filename}")
    return competition, current_date


def save_records_to_file(record_book: RecordBook, filename: str = "records_data.json") -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(record_book.to_dict(), f, indent=2, ensure_ascii=False)
    print(f"Saved records to {filename}")


def load_records_from_file(filename: str = "records_data.json") -> RecordBook:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        book = RecordBook.from_dict(data)
        print(f"Loaded records from {filename}")
        return book
    except FileNotFoundError:
        print("No records file found. Starting fresh record book.")
        return RecordBook()
    
def save_world_state(
    nations: dict,
    tier_seasons: dict,
    committed_tiers: dict,
    prev_season_results: dict,
    filename: str = "world_state.json",
) -> None:
    """
    Persist nation prestige, tier guard state, and previous-season competition
    results between sessions.
 
    prev_season_results carries the four winner/runner-up names needed by
    _start_season() to resolve supercup participants:
        {
            "league_winner":    str | None,
            "league_runner_up": str | None,
            "cup_winner":       str | None,
            "cup_runner_up":    str | None,
        }
 
    Why a separate file from teams_data.json?
    Nation data is world-level; team data is club-level.
    Keeping them separate means you can reset clubs without
    losing world history, and vice versa.
    """
    data = {
        "nation_prestige": {nid: n.prestige for nid, n in nations.items()},
        "tier_seasons": tier_seasons,
        "committed_tiers": committed_tiers,
        "prev_season_results": prev_season_results or {},
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved world state to {filename}")
    
def load_world_state(
    nations: dict,
    filename: str = "world_state.json",
) -> tuple[dict, dict, dict]:
    """
    Load nation prestige, tier guard state, and previous-season results,
    updating NationConfig objects in place.
 
    Returns (tier_seasons, committed_tiers, prev_season_results).
    If no file exists, returns empty dicts — nations keep their YAML prestige values.
 
    Why update NationConfig objects in place?
    Because the rest of the codebase already holds references to them.
    Replacing the objects would silently break every caller that did
    `nation = get_nation("myria")` before this function ran.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for nation_id, prestige in data.get("nation_prestige", {}).items():
            if nation_id in nations:
                nations[nation_id].prestige = prestige

        print(f"Loaded prestige for {len(nations)} nations from {filename}")
        return (data.get("tier_seasons", {}), 
                data.get("committed_tiers", {}), 
                data.get("prev_season_results", {})
        )
        
    except FileNotFoundError:
        print("No world state file found. Starting with YAML prestige values and empty tier guards.")
        return {}, {}, {}