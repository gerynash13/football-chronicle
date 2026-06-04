import json
import datetime
import random
try:
    from classes import Team, Player
except ModuleNotFoundError:
    from team import Team
    from player import Player
from records import RecordBook
from player_refs import new_player_id

def save_teams_to_file(teams, filename="teams_data.json"):
    data = []

    for team in teams:
        team_data = {
            "name":             team.name,
            "nation_id":        team.nation_id,
            "league_nation_id": team.league_nation_id,
            "attack":           team.attack,
            "midfield":         team.midfield,
            "defense":          team.defense,
            "squad":            [],
            "morale":           team.morale,
            "board_confidence": team.board_confidence,
            "fan_satisfaction": team.fan_satisfaction,
            "prestige":         team.prestige,
            "home_region":      team.home_region,
            "budget":           team.budget,
            "wage_budget":      team.wage_budget,
        }

        for player in team.squad:
            player_data = {
                "id":                   player.id,
                "name":                 player.name,
                "position":             player.position,
                "birth_date":           player.birth_date.isoformat(),
                "current_ability":      player.current_ability,
                "potential_ability":    player.potential_ability,
                "nationality":          player.nationality,
                "parent_nationality":   player.parent_nationality,
                "birth_region":         player.birth_region,
                "preferred_foot":       player.preferred_foot,
                "contract_expires":     player.contract_expires,
                "wage":                 player.wage,
                "is_retired":           player.is_retired,
                "morale":               player.morale,
                "manager_relationship": player.manager_relationship,

                # Season stats
                "goals":                    player.goals,
                "assists":                  player.assists,
                "appearances":              player.appearances,
                "clean_sheets":             player.clean_sheets,
                "season_avg_rating":        player.season_avg_rating,
                "season_rating_appearances": player.season_rating_appearances,
                "yellow_cards":             player.yellow_cards,
                "red_cards":                player.red_cards,
                "is_suspended":             player.is_suspended,
                "suspension_matches_left":  player.suspension_matches_left,
                "is_injured":               player.is_injured,
                "injury_matches_left":      player.injury_matches_left,
                "injury_severity":          player.injury_severity,

                # Career stats
                "career_goals":        player.career_goals,
                "career_assists":      player.career_assists,
                "career_appearances":  player.career_appearances,
                "career_clean_sheets": player.career_clean_sheets,
                "career_yellow_cards": player.career_yellow_cards,
                "career_red_cards":    player.career_red_cards,
                "career_injuries":     player.career_injuries,

                # Career history and flags
                "career_history":  player.career_history,
                "is_wonderkid":    player.is_wonderkid,
            }
            team_data["squad"].append(player_data)
        
        data.append(team_data)
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(teams)} teams to {filename}")

def load_teams_from_file(file_path):
    teams = []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for team_data in data:
        team = Team(
          name=team_data["name"],
          attack = team_data["attack"],
          midfield = team_data["midfield"],
          defense = team_data["defense"]
          )
        
        team.morale           = team_data.get("morale", 0.0)
        team.board_confidence = team_data.get("board_confidence", 50.0)
        team.fan_satisfaction = team_data.get("fan_satisfaction", 50.0)
        team.prestige         = team_data.get("prestige", 500.0)
        team.home_region      = team_data.get("home_region", "")
        team.budget           = team_data.get("budget", 1000)
        team.wage_budget      = team_data.get("wage_budget", 300)
        team.nation_id        = team_data.get("nation_id", "")
        team.league_nation_id = team_data.get("league_nation_id", "")

        for player_data in team_data.get("squad", []):
            # ── Birth date — with backward-compat fallback for old saves ──────
            # Old saves stored "age" as an integer. New saves store "birth_date"
            # as an ISO string. We support both so existing saves don't break.
            if "birth_date" in player_data:
                birth_date = datetime.date.fromisoformat(player_data["birth_date"])
            else:
                # Reconstruct an approximate birth date from the old age field.
                # We don't know the real birth year, so we estimate from the
                # save file itself (no perfect solution — this is a one-time
                # migration path for saves that predate birth_date).
                age = player_data.get("age", 25)
                approx_year = datetime.date.today().year - age
                birth_date  = datetime.date(
                    approx_year,
                    random.randint(1, 12),
                    random.randint(1, 28),
                )

            player = Player(
                name              = player_data["name"],
                position          = player_data["position"],
                birth_date        = birth_date,
                current_ability   = player_data["current_ability"],
                potential_ability = player_data["potential_ability"],
                player_id         = player_data.get("id") or new_player_id(),
                nationality        = player_data.get("nationality"),
                parent_nationality= player_data.get("parent_nationality"),
                birth_region      = player_data.get("birth_region"),
                preferred_foot    = player_data.get("preferred_foot"),
                contract_expires  = player_data.get("contract_expires"),
                wage              = player_data.get("wage", 0),
            )

            # Status fields
            player.is_retired           = player_data.get("is_retired", False)
            player.morale               = player_data.get("morale", 0.0)
            player.manager_relationship = player_data.get("manager_relationship", 0.0)

            # Season stats
            player.goals                     = player_data.get("goals", 0)
            player.assists                   = player_data.get("assists", 0)
            player.appearances               = player_data.get("appearances", 0)
            player.clean_sheets              = player_data.get("clean_sheets", 0)
            player.season_avg_rating         = player_data.get("season_avg_rating", 0.0)
            player.season_rating_appearances = player_data.get("season_rating_appearances", 0)
            player.yellow_cards              = player_data.get("yellow_cards", 0)
            player.red_cards                 = player_data.get("red_cards", 0)
            player.is_suspended              = player_data.get("is_suspended", False)
            player.suspension_matches_left   = player_data.get("suspension_matches_left", 0)
            player.is_injured                = player_data.get("is_injured", False)
            player.injury_matches_left       = player_data.get("injury_matches_left", 0)
            player.injury_severity           = player_data.get("injury_severity", None)

            # Career stats
            player.career_goals        = player_data.get("career_goals", 0)
            player.career_assists      = player_data.get("career_assists", 0)
            player.career_appearances  = player_data.get("career_appearances", 0)
            player.career_clean_sheets = player_data.get("career_clean_sheets", 0)
            player.career_yellow_cards = player_data.get("career_yellow_cards", 0)
            player.career_red_cards    = player_data.get("career_red_cards", 0)
            player.career_injuries     = player_data.get("career_injuries", 0)

            # Career history and flags
            player.career_history = player_data.get("career_history", [])
            player.is_wonderkid   = player_data.get("is_wonderkid", False)

            team.squad.append(player)
    
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
    filename: str = "world_state.json",
) -> None:
    """
    Persist nation prestige and tier guard state between sessions.

    Why a separate file from teams_data.json?
    Nation data is world-level; team data is club-level.
    Keeping them separate means you can reset clubs without
    losing world history, and vice versa.
    """
    data = {
        "nation_prestige": {nid: n.prestige for nid, n in nations.items()},
        "tier_seasons": tier_seasons,
        "committed_tiers": committed_tiers,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved world state to {filename}")
    
def load_world_state(
    nations: dict,
    filename: str = "world_state.json",
) -> tuple[dict, dict]:
    """
    Load nation prestige and tier guard state, updating NationConfig objects in place.

    Returns (tier_seasons, committed_tiers) so the engine can store them.
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
        return data.get("tier_seasons", {}), data.get("committed_tiers", {})
        
    except FileNotFoundError:
        print("No world state file found. Starting with YAML prestige values and empty tier guards.")
        return {}, {}