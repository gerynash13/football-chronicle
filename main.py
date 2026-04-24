import random
import json
import os
from classes.team import Team
from classes.player import Player
from classes.competition import Competition
from simulation import simulate_match
from name_generator import generate_myrian_name, generate_squad
from data_manager import save_teams_to_file, load_teams_from_file

sulhavon = Team("Kluba Sulhavonos", 64, 58, 57)
maritima_thesia = Team("Kluba Maritima Thesias", 62, 61, 64)
mercaria = Team("Mercaria Kluba", 60, 64, 62)
portavar = Team("Portavar Kluba", 60, 58, 59)
esalum = Team("Kluba Sportika Esalumou", 56, 58, 57)
mileius = Team("Kluba Sportika Mileiu", 58, 56, 59)
galvonon = Team("Kluba Sportika Galvononos", 63, 65, 60)
pk_galvonon = Team("Populara Kluba Galvononos", 61, 60, 61)
gedium = Team("Kluba Sportika Gedimou", 58, 59, 61)
soleium = Team("Kluba Sportika Soleiu", 57, 60, 58)
metia = Team("Kluba Maritima Metia", 55, 55, 56)
alentum = Team("Kluba Sportika Alentumou", 59, 61, 60)

south_thesia = Team("Kluba Notias Thesias", 48, 50, 49)
burium = Team("Kluba Sportika Buriou", 43, 45, 44)
sufelhar = Team("Kluba Sportika Sufelharos", 40, 41, 42)
eleica = Team("Kluba Sportika Eleicas", 44, 43, 45)
drosvon = Team("Kluba Potamia Drosvon", 40, 42, 41)
ancivon = Team("Kluba Sportika Ancivonos", 39, 40, 38)
nalhavon = Team("Brakika Kluba Nalhavonos", 41, 38, 39)
malia = Team("Kluba Pyron Malias", 40, 41, 43)
novius = Team("Kluba Sportika Noviou", 40, 42, 41)
lunara = Team("Kluba Sportika Lunaras", 38, 39, 38)
amana = Team("Kluba Emvaria Amanas", 38, 40, 39)
ircenta = Team("Kluba Sportika Ircentas", 37, 38, 36)
skriptavon = Team("Kluba tou Skriptavonos", 41, 44, 40)
coraerum = Team("Kluba Sportika Coraerou", 40, 41, 40)

veldhavon = Team("Kluba Veldhavonos", 39, 38, 40)

teams = [sulhavon, maritima_thesia, mercaria, portavar, esalum, mileius, galvonon, pk_galvonon, gedium, soleium, metia, alentum]

if os.path.exists("teams_data.json"):
    teams = load_teams_from_file("teams_data.json")
else:
    print("No teams data found. Generating new teams...")
    for team in teams:
        avg_ca = int((team.attack + team.midfield + team.defense) / 3)
        team.squad = generate_squad(team.name, average_ca=avg_ca)

    save_teams_to_file(teams)


standings = {}
match_results = []

for team in teams:
    standings[team.name] = {
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0
    }

for home_team in teams:
    for away_team in teams:
        if home_team != away_team:
            home_goals, away_goals = simulate_match(home_team, away_team)

            match_results.append({
                "home_team": home_team.name,
                "away_team": away_team.name,
                "home_goals": home_goals,
                "away_goals": away_goals
            })

            # Update standings for both teams
            standings[home_team.name]["played"] += 1
            standings[away_team.name]["played"] += 1

            standings[home_team.name]["goals_for"] += home_goals
            standings[away_team.name]["goals_for"] += away_goals

            standings[home_team.name]["goals_against"] += away_goals
            standings[away_team.name]["goals_against"] += home_goals

            standings[home_team.name]["goal_difference"] = standings[home_team.name]["goals_for"] - standings[home_team.name]["goals_against"]
            standings[away_team.name]["goal_difference"] = standings[away_team.name]["goals_for"] - standings[away_team.name]["goals_against"]

            # Determine points and W-D-L record
            if home_goals > away_goals:
                standings[home_team.name]["wins"] += 1
                standings[home_team.name]["points"] += 3
                standings[away_team.name]["losses"] += 1
            elif away_goals > home_goals:
                standings[away_team.name]["wins"] += 1
                standings[away_team.name]["points"] += 3
                standings[home_team.name]["losses"] += 1
            else:
                standings[home_team.name]["draws"] += 1
                standings[home_team.name]["points"] += 1
                standings[away_team.name]["draws"] += 1
                standings[away_team.name]["points"] += 1

            print(f"\n{home_team.name} {home_goals} - {away_goals} {away_team.name}")
            print("="*50)

sorted_standings = sorted(standings.items(), key=lambda x: x[1]["points"], reverse=True)

print("\n" + "="*80)
print("LEAGUE TABLE")
print("="*80)
print(f"{'Pos':<5} {'Team':<30} {'GP':<5} {'W':<5} {'D':<5} {'L':<5} {'GF':<5} {'GA':<5} {'GD':<5} {'Pts':<5}")
print("-"*80)

position = 1
for team_name, stats in sorted_standings:
    print(f"{position:<5} {team_name:<30} {stats['played']:<5} {stats['wins']:<5} {stats['draws']:<5} {stats['losses']:<5} {stats['goals_for']:<5} {stats['goals_against']:<5} {stats['goal_difference']:<5} {stats['points']:<5}")
    position += 1

print("="*80)

# Save standings
with open("league_table.txt", "w", encoding="utf-8") as f:
    f.write("="*80 + "\n")
    f.write("LEAGUE TABLE\n")
    f.write("="*80 + "\n")
    f.write(f"{'Pos':<5} {'Team':<30} {'P':<5} {'W':<5} {'D':<5} {'L':<5} {'GF':<5} {'GA':<5} {'GD':<5} {'Pts':<5}\n")
    f.write("-"*80 + "\n")
    
    position = 1
    for team_name, stats in sorted_standings:
        f.write(f"{position:<5} {team_name:<30} {stats['played']:<5} {stats['wins']:<5} {stats['draws']:<5} {stats['losses']:<5} {stats['goals_for']:<5} {stats['goals_against']:<5} {stats['goal_difference']:<5} {stats['points']:<5}\n")
        position += 1
    
    f.write("="*80 + "\n")
    
all_players = []
for team in teams:
    all_players.extend(team.squad)

top_scorers = sorted(all_players, key=lambda p: p.goals, reverse=True)[:10]
top_assisters = sorted(all_players, key=lambda p: p.assists, reverse=True)[:10]

# Display
print("\n" + "="*80)
print("TOP 10 SCORERS")
print("="*80)
print(f"{'Rank':<5} {'Name':<30} {'Team':<30} {'Goals':<5}")
print("-"*80)

for i, player in enumerate(top_scorers, 1):
    player_team = next(t.name for t in teams if player in t.squad)
    print(f"{i:<5} {player.name:<30} {player_team:<30} {player.goals:<5}")

print("="*80)

print("\n" + "="*80)
print("TOP 10 ASSISTERS")
print("="*80)
print(f"{'Rank':<5} {'Name':<30} {'Team':<30} {'Assists':<5}")
print("-"*80)

for i, player in enumerate(top_assisters, 1):
    player_team = next(t.name for t in teams if player in t.squad)
    print(f"{i:<5} {player.name:<30} {player_team:<30} {player.assists:<5}")

print("="*80)

print("League table saved to league_table.txt")

with open("match_results.json", "w", encoding="utf-8") as f:
    json.dump(match_results, f, indent=2, ensure_ascii=False)

print("Match results saved to match_results.json")

for team in teams:
    avg_ca = (team.attack + team.midfield + team.defense) / 3
    team_squad = generate_squad(team.name, average_ca=avg_ca)
    print(f"Generated squad for {team.name} (avg CA: {round(avg_ca)})") 

save_teams_to_file(teams)
print("Teams data saved to teams_data.json")

loaded_teams = load_teams_from_file("teams_data.json")
