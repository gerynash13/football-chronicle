import random
import json
import os
from classes import Team, Player, Competition
from name_generator import generate_squad
from data_manager import save_teams_to_file, load_teams_from_file, save_competition_to_file, load_competition_data

# Display standings after matchday
def print_standings(standings, title="STANDINGS"):
    "Print formatted league table"
    sorted_standings = sort_standings(standings)
    
    print(f"\n{'='*80}")
    print(title)
    print(f"{'='*80}\n")
    print(f"{'Pos':<5}{'Team':<30}{'GP':<4}{'W':<4}{'D':<4}{'L':<4}{'GF':<4}{'GA':<4}{'GD':<5}{'Pts':<4}")
    print(f"{'-'*80}")
    
    for i, (team_name, stats) in enumerate(sorted_standings, 1):
        print(f"{i:<5}{team_name:<30}{stats['played']:<4}{stats['wins']:<4}"
            f"{stats['draws']:<4}{stats['losses']:<4}{stats['goals_for']:<4}"
            f"{stats['goals_against']:<4}{stats['goal_difference']:<5}{stats['points']:<4}")
    
    print(f"{'='*80}\n")
    
def print_match_result(result):
    """Display a single match with goals and events"""
    home = result["home_team"]
    away = result["away_team"]
    home_goals = result["home_goals"]
    away_goals = result["away_goals"]
    events = result.get("events", [])
    
    # Match header
    print(f"\n{'-'*80}")
    print(f"         {home:^25} {home_goals} - {away_goals} {away:^25}  ")
    print(f"{'-'*80}\n")
    
    # Get goal events
    goals = [e for e in events if e["type"] == "goal"]
    
    if goals:
        print("\n⚽ GOALS:")
        for goal in goals:
            assister = f" ({goal['assister']})" if "assister" in goal else ""
            print(f"  {goal['minute']} - {goal['player']}{assister} [{goal['team']}]")
    else:
        print("\n  No goals scored.")
            
    # Shot stats
    home_shots_on = sum(1 for e in events if e["team"] == home and e['type'] == "shot_on_target")
    home_shots_off = sum(1 for e in events if e["team"] == home and e['type'] == "shot_off_target")
    away_shots_on = sum(1 for e in events if e["team"] == away and e['type'] == "shot_on_target")
    away_shots_off = sum(1 for e in events if e["team"] == away and e['type'] == "shot_off_target")
    
    print("\n📊 MATCH STATS:")
    print(f"  Shots on target: {home_shots_on} - {away_shots_on}")
    print(f"  Shots off target: {home_shots_off} - {away_shots_off}")
    
    
def sort_standings(standings):
    """Sort standings with proper tiebreakers"""
    return sorted(
        standings.items(),
        key=lambda x: (
            -x[1]["points"],
            -x[1]["goal_difference"],
            -x[1]["goals_for"],
            x[0]
        )        
    )

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
    print("No teams data found. Generating new squads...")
    for team in teams:
        avg_ca = int((team.attack + team.midfield + team.defense) / 3)
        team.squad = generate_squad(team.name, average_ca=avg_ca)

    save_teams_to_file(teams)
    
# Create competition
comp = Competition("Prote Kategorias", teams)
comp.generate_fixtures()

if os.path.exists("competition_data.json"):
    response = input("Do you want to load the saved state? (y/n): ")
    if response.lower() == "y":
        comp = load_competition_data(comp)
        print(f"Resumed at matchday {comp.current_matchday}")
    else:
        # Start new save
        os.remove("competition_data.json")

# Simulate season (matchday by matchday)
while comp.current_matchday <= comp.total_rounds:
    print(f"\n{'='*80}")
    print(f"Matchday {comp.current_matchday}")
    print(f"{'='*80}\n")
    
    # Show fixtures
    fixtures = comp.get_current_fixtures()
    for fixture in fixtures:
        print(f"{fixture['home_team'].name} vs {fixture['away_team'].name}\n")
        
    # Simulate matchday
    comp.simulate_matchday()
    
    # Show match results
    print(f"\n{'-'*80}")
    print(f"Matchday {comp.current_matchday} results")
    print(f"{'-'*80}\n")
    
    matches_per_matchday = len(comp.teams) // 2
    recent_results = comp.results[-matches_per_matchday:]
    
    for result in recent_results:
        print_match_result(result)
        
    # Display standings
    print_standings(comp.standings, f"STANDINGS AFTER MATCHDAY {comp.current_matchday}")
    
    # Save after every matchday
    save_competition_to_file(comp)
        
    # Advance to next matchday
    if comp.current_matchday < comp.total_rounds:
        comp.advance_matchday()
    else:
        break
    
# Season completed - show final stats
print(f"\n{'='*80}")
print(f"Final Standings")
print(f"{'='*80}\n")

# Champion
champion = sort_standings(comp.standings)[0]
print(f"🏆 Champion: {champion[0]} - {champion[1]['points']} pts")

# Top scorers and assisters
all_players = []
for team in teams:
    all_players.extend(team.squad)
    
top_scorers = sorted(all_players, key=lambda p: p.goals, reverse=True)[:10]
top_assisters = sorted(all_players, key=lambda p: p.assists, reverse=True)[:10]

print(f"\n{'='*80}")
print(f"Top Scorers")
print(f"{'='*80}\n")
print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Goals':<4}")
print(f"{'-'*80}")

for i, player in enumerate(top_scorers, 1):
    player_team = next(t for t in teams if player in t.squad)
    print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.goals:<4}")
    
print(f"\n{'='*80}")

print(f"\n" + "="*80)
print(f"Top Assisters")
print(f"{'='*80}\n")
print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Assists':<4}")
print(f"{'-'*80}")

for i, player in enumerate(top_assisters, 1):
    player_team = next(t for t in teams if player in t.squad)
    print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.assists:<4}")
    
print(f"\n{'='*80}")

# Save final state
save_teams_to_file(teams)
print("\nSeason completed. Data saved to teams_data.json")

# Delete competition state file after season
if os.path.exists("competition_data.json"):
    os.remove("competition_data.json")
    print("Competition state cleared - ready for next season!")