import json
from classes import Team, Player

def save_teams_to_file(teams, filename="teams_data.json"):
    data = []

    for team in teams:
        team_data = {
            "name": team.name,
            "attack": team.attack,
            "midfield": team.midfield,
            "defense": team.defense,
            "squad": []
        }

        for player in team.squad:
            player_data = {
                "name": player.name,
                "position": player.position,
                "age": player.age,
                "current_ability": player.current_ability,
                "potential_ability": player.potential_ability,
                
                # Season stats
                "goals": player.goals,
                "assists": player.assists,
                "appearances": player.appearances,
                "clean_sheets": player.clean_sheets,
                "season_avg_rating": player.season_avg_rating,
                "season_rating_appearances": player.season_rating_appearances,
                
                # Career stats
                "career_goals": player.career_goals,
                "career_assists": player.career_assists,
                "career_appearances": player.career_appearances,
                "career_clean_sheets": player.career_clean_sheets,
                
                # Career history
                "career_history": player.career_history,
                
                # Wonderkid flag
                "is_wonderkid": player.is_wonderkid
                
                
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

        for player_data in team_data.get("squad", []):
            player = Player(
              name = player_data["name"],
              position = player_data["position"],
              age = player_data["age"],
              current_ability = player_data["current_ability"],
              potential_ability = player_data["potential_ability"]
              )
            
            # Load season stats  
            player.goals = player_data.get("goals", 0)
            player.assists = player_data.get("assists", 0)
            player.appearances = player_data.get("appearances", 0)
            player.season_avg_rating = player_data.get("season_avg_rating", 0.0)
            player.season_rating_appearances = player_data.get("season_rating_appearances", 0)
            
            # Load career stats
            player.career_goals = player_data.get("career_goals", 0)
            player.career_assists = player_data.get("career_assists", 0)
            player.career_appearances = player_data.get("career_appearances", 0)
            
            # Load career history
            player.career_history = player_data.get("career_history", [])
            
            # Load wonderkid flag
            player.is_wonderkid = player_data.get("is_wonderkid", False)
              
            team.squad.append(player)
    
        teams.append(team)
    
    return teams

def save_competition_to_file(competition, filename="competition_data.json"):
    """Save competition to resume later"""
    
    # Convert results to JSON-friendly format
    serializable_results = []
    for result in competition.results:
        serializable_result = {
            "home_team": result["home_team"],
            "away_team": result["away_team"],
            "home_goals": result["home_goals"],
            "away_goals": result["away_goals"],
            "events": result.get("events", [])
        }
        serializable_results.append(serializable_result)
        
    comp_data = {
        "name": competition.name,
        "type": competition.type,
        "current_matchday": competition.current_matchday,
        "standings": competition.standings,
        "results": serializable_results,
        "completed_matchdays": list(competition.completed_matchdays)
    }
        
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(comp_data, f, indent=2, ensure_ascii=False)

    print(f"Saved competition to {filename}")
    
    
def load_competition_data(competition, filename="competition_data.json"):
    """Load saved competition state into a competition object"""
    with open(filename, "r", encoding="utf-8") as f:
        comp_data = json.load(f)
        
    competition.current_matchday = comp_data["current_matchday"]
    competition.standings = comp_data["standings"]
    
    competition.results = comp_data["results"]
    competition.completed_matchdays = set(comp_data.get("completed_matchdays", []))
    
    print(f"Loaded competition state from {filename}")
    return competition