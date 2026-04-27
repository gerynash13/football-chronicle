import random
import json
import os
from classes import Team, Player, Competition
from name_generator import generate_squad
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
    print("No teams data found. Generating new squads...")
    for team in teams:
        avg_ca = int((team.attack + team.midfield + team.defense) / 3)
        team.squad = generate_squad(team.name, average_ca=avg_ca)

    save_teams_to_file(teams)
    
# Create competition
comp = Competition("Prote Kategorias", teams)
comp.generate_fixtures()

# Simulate season (matchday by matchday)
while comp.current_matchday <= len(comp.fixtures):
    print(f"\n{'='*80}")
    print(f"Matchday {comp.current_matchday}")
    print(f"{'='*80}\n")
    
    # Show fixtures
    fixtures = comp.get_current_fixtures()
    for fixture in fixtures:
        print(f"{fixture['home_team'].name} vs {fixture['away_team'].name}")
        
    # Simulate matchday
    comp.simulate_matchday()
    
    # Display standings after matchday
    sorted_standings = sorted(comp.standings.items(), key=lambda x: x[1]["points"], reverse=True)
    
    print(f"\n{'='*80}")
    print(f"Standings after Matchday {comp.current_matchday}")
    print(f"{'='*80}\n")
    print(f"{'Pos':<6}{'Team':<30}{'GP':<5}{'W':<5}{'D':<5}{'L':<5}{'GF':<5}{'GA':<5}{'GD':<5}{'Pts':<5}")
    print(f"{'-'*80}")
    
    for i, (team_name, stats) in enumerate(sorted_standings, 1):
        print(f"{i:<5} {team_name:<30} {stats['played']:<4} {stats['wins']:<4} {stats['draws']:<4} {stats['losses']:<4} {stats['goals_for']:<4} {stats['goals_against']:<4} {stats['goal_difference']:<4} {stats['points']:<4}")
        
    print(f"\n{'='*80}\n")
    
    # Advance to next matchday
    if comp.current_matchday < len(comp.fixtures):
        comp.advance_matchday()
    else:
        break
    
# Season completed - show final stats
print(f"\n{'='*80}")
print(f"Final Standings")
print(f"{'='*80}\n")

# Champion
champion = sorted(comp.standings.items(), key=lambda x: x[1]["points"], reverse=True)[0]
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