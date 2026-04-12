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
                "goals": player.goals,
                "assists": player.assists,
                "appearances": player.appearances
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
          name=team.data["name"],
          attack = team.data["attack"],
          midfield = team.data["midfield"],
          defense = team.data["defense"]
          )

        for player_data in team_data.get("squad", []):
            player = Player(
              name = player_data["name"],
              position = player_data["position"],
              age = player_data["age"],
              current_ability = player_data["current_ability"],
              potential_ability = ["potential_ability"]
              )
              
              player.goals = player_data.get("goals", 0)
              player.assists = player_data.get(assists, 0)
              player.appearances = player_data.get(appearances, 0)
              
              player._generate_attributes()
              player._determine_role()
              
            team.squad.append(player)
    
        teams.append(team)
    
    return teams