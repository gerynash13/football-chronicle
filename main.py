import random
import json
import os
import datetime
from classes import Team, Player, Competition, Season
from name_generator import generate_squad
from data_manager import save_teams_to_file, load_teams_from_file, save_competition_to_file, load_competition_data
from game_calendar import GameCalendar, apply_effects, apply_match_morale
from rules import get_max_subs, get_card_rules, get_yellow_threshold
from events import Event, Effect
from simulation import roll_injury_severity

FORMATION = {
    "GK": 1,
    "DEF": 2,
    "MID": 3,
    "FWD": 5
}

def run_season(season_year, teams):
    
    # Create season:
    current_season = Season(season_year, teams)
    
    # Create competition
    comp = Competition(
        "Prote Kategorias", teams, 
        max_subs=get_max_subs(season_year),
        season_year=season_year
    )
    comp.generate_fixtures()
    current_season.add_competition(comp)
    
    calendar = GameCalendar(season_year)
    calendar.schedule_fixtures(comp)
    
    # Check for saved state:
    if os.path.exists("competition_data.json"):
        response = input("Do you want to load the saved state? (y/n): ")
        if response.lower() == "y":
            comp, saved_date = load_competition_data(comp)
            calendar.schedule_fixtures(comp)  # Reschedule in case there are any differences
            calendar.current_date = saved_date
            print(f"Resumed at {calendar.current_date.strftime('%A, %d %B %Y')}, Matchday {comp.current_matchday}")
        else:
            # Start new save
            os.remove("competition_data.json")
            
    last_processed = calendar.current_date
    
    # Main date-driven loop
    while calendar.current_date <= calendar.season_end:
        next_date = calendar.get_next_event_date(calendar.current_date)
        
        if next_date is None or next_date > calendar.season_end:
            break  # No more events or past season end
        
        # Apply weekly decay on the first day of each week
        d = last_processed
        while d <= next_date:
            if d.weekday() == 0:  # Monday
                calendar.apply_weekly_decay(teams)
            d += datetime.timedelta(days=1)
            
        calendar.current_date   = next_date
        events_today            = calendar.get_events_for_date(calendar.current_date)
        dynamic                 = calendar.roll_dynamic_events(teams)
        all_events              = events_today + dynamic
        
        background = [e for e in all_events if not e.blocking]
        blocking   = [e for e in all_events if e.blocking]
        
        # Background events - silent, straight to inbox
        for event in background:
            apply_effects(event.effects, teams)
            calendar.inbox.append(event)
            
        # Blocking events - stop the world, show them, and apply effects immediately
        if blocking:
            match_events = [e for e in all_events if e.category == "match"]
            
            if match_events:
                today_fixtures = [f for f in comp.fixtures
                                  if f.get("date") == calendar.current_date]
                
                if today_fixtures:
                    matchday_num = today_fixtures[0]["matchday"]
                    
                    if matchday_num not in comp.completed_matchdays:
                        print(f"\n{'='*80}")
                        print(f"   {calendar.current_date.strftime('%A, %d %B %Y')}")
                        print(f"   Matchday {matchday_num}")
                        print(f"{'='*80}\n")
                        
                        for f in today_fixtures:
                            print(f"   {f['home_team'].name} vs {f['away_team'].name}")
                            
                    comp.current_matchday = matchday_num
                    comp.simulate_matchday()
                    
                    print(f"\n{'='*80}")
                    print(f"   Matchday {matchday_num} Results")
                    print(f"{'='*80}\n")
                    
                    recent = comp.results[-len(today_fixtures):]
                    for result in recent:
                        print_match_result(result)
                        
                        home_team = next((t for t in teams if t.name == result["home_team"]), None)
                        away_team = next((t for t in teams if t.name == result["away_team"]), None)
                        if home_team and away_team:
                            apply_match_morale(home_team, away_team, result["home_goals"], result["away_goals"])
                    
                    # Yellow card accumulation check
                    YELLOW_THRESHOLD = get_yellow_threshold(season_year)
                    for team in teams:
                        for player in team.squad:
                            if (player.yellow_cards > 0
                                and player.yellow_cards % YELLOW_THRESHOLD == 0
                                and not player.is_suspended):
                                player.is_suspended = True
                                player.suspension_matches_left = 1
                                player.yellow_cards -= YELLOW_THRESHOLD
                                
                    # Suspension and injury countdown
                    for team in teams:
                        for player in team.squad:
                            if player.suspension_matches_left > 0:
                                player.suspension_matches_left -= 1
                                if player.suspension_matches_left == 0:
                                    player.is_suspended = False
                            if player.injury_matches_left > 0:
                                player.injury_matches_left -= 1
                                if player.injury_matches_left == 0:
                                    player.is_injured = False
                                    player.injury_severity = None
                                    
                    # Off-match injury roll
                    OFF_MATCH_INJURY_CHANCE = 0.01
                    for team in teams:
                        for player in team.squad:
                            if not player.is_injured and random.random() < OFF_MATCH_INJURY_CHANCE:
                                severity, matches_out = roll_injury_severity()
                                player.is_injured = True
                                player.injury_matches_left = matches_out
                                player.injury_severity = severity
                                player.career_injuries += 1
                                calendar.schedule_injury_notification(player, team, calendar.current_date)
                                
                    # In-match injuries (schedule notifications for those flagged during simulation)
                    for result in recent:
                        injury_events = [e for e in result.get("events", []) if e["type"] == "injury"]
                        for inj_evt in injury_events:
                            for team in teams:
                                player = next((p for p in team.squad if p.name == inj_evt["player"]), None)
                                if player:
                                    calendar.schedule_injury_notification(player, team, calendar.current_date)
                                    break
                            
                    for team in teams:
                        for player in team.squad:
                            if player.morale < -2.0:
                                calendar.schedule_player_meeting(player, team, calendar.current_date)
                                
                    calendar.generate_newspaper_story(teams, comp)
                            
                    print_standings(comp.standings, f"STANDINGS - {calendar.current_date.strftime('%d %B %Y')}")
                    
                    save_competition_to_file(comp, calendar.current_date)
                    
            # Non-match blocking events (stub - to be expanded as we add more event types)
            for event in [e for e in blocking if e.category != "match"]:
                print(f"\n{'='*80}")
                print(f"  {event.title}")
                print(f"  {event.description}")
                if event.choices:
                    for i, choice in enumerate(event.choices, 1):
                        print(f"    [{i}] {choice.text}")
                    print()
                    while True:
                        try:
                            pick = int(input("Enter your choice: ")) -1
                            if 0 <= pick < len(event.choices):
                                chosen = event.choices[pick]
                                apply_effects(chosen.effects, teams)
                                event.resolution = chosen.text
                                event.is_read = True
                                print(f"\n{chosen.text}")
                                break
                            else:
                                print("  Enter a number between 1 and {len(event.choices)}.")
                        except ValueError:
                            print("  Enter a number between 1 and {len(event.choices)}.")
                else:
                    apply_effects(event.effects, teams)
                    event.is_read = True
                    input("\nPress Enter to continue...")
                print(f"{'='*80}\n")
                
            # Advance prompt - tell the user what's next and wait for input to proceed
            next_upcoming = calendar.get_next_event_date(
                calendar.current_date + datetime.timedelta(days=1)
            )
            if next_upcoming and next_upcoming <= calendar.season_end:
                print(f"Next scheduled event: {next_upcoming.strftime('%A, %d %B %Y')}")
                input("Press Enter to continue...")
            else:
                print("No more scheduled events. Advancing to season end...")
                break
                
        last_processed = calendar.current_date
        calendar.current_date += datetime.timedelta(days=1)
        
    # Season completed - show final stats
    print(f"\n{'='*80}")
    print(f"Final Standings")
    print(f"{'='*80}\n")
    
    # Champion
    champion = sort_standings(comp.standings)[0]
    print(f"🏆 Champion: {champion[0]} - {champion[1]['points']} points")
    
    # Top scorers and assisters
    all_players = [p for t in teams for p in t.squad]
    
    top_scorers = sorted(all_players, key=lambda p: p.goals, reverse=True)[:10]
    top_assisters = sorted(all_players, key=lambda p: p.assists, reverse=True)[:10]
    top_clean_sheets = sorted([p for p in all_players if p.position == "GK"], 
                              key=lambda p: p.clean_sheets, 
                              reverse=True)[:10]
    
    print(f"\n{'='*80}")
    print(f"Top Scorers - {season_year}")
    print(f"{'='*80}\n")
    print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Goals':<4}")
    print(f"{'-'*80}")
    
    for i, player in enumerate(top_scorers, 1):
        player_team = next(t for t in teams if player in t.squad)
        print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.goals:<4}")
        
    print(f"\n{'='*80}")
    print(f"Top Assisters - {season_year}")
    print(f"{'='*80}\n")
    print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Assists':<4}")
    print(f"{'-'*80}")
    
    for i, player in enumerate(top_assisters, 1):
        player_team = next(t for t in teams if player in t.squad)
        print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.assists:<4}")
        
    print(f"\n{'='*80}")
    print(f"Top Clean Sheets - {season_year}")
    print(f"{'='*80}\n")
    print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Clean Sheets':<4}")
    print(f"{'-'*80}")
    
    for i, player in enumerate(top_clean_sheets, 1):
        player_team = next(t for t in teams if player in t.squad)
        print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.clean_sheets:<4}")
        
    top_rated = sorted(
        [p for p in all_players if p.season_rating_appearances >= 5],
        key=lambda p: p.season_avg_rating, 
        reverse=True
    )[:10]
    
    print(f"\n{'='*80}")
    print(f"Top Rated Players - {season_year} Season")
    print(f"{'='*80}\n")
    print(f"{'Rank':<5}{'Name':<30}{'Team':<30}{'Avg Rating':<6}")
    print(f"{'-'*80}")
    
    for i, player in enumerate(top_rated, 1):
        player_team = next(t for t in teams if player in t.squad)
        print(f"{i:<5} {player.name:<30} {player_team.name:<30} {player.season_avg_rating:<6.2f}")
        
    # End season
    current_season.end_season()
    
    # Clean up
    if os.path.exists("competition_data.json"):
        os.remove("competition_data.json")
        
    return teams

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
    home        = result["home_team"]
    away        = result["away_team"]
    home_goals  = result["home_goals"]
    away_goals  = result["away_goals"]
    events      = result.get("events", [])
    ratings     = result.get("ratings", {})
    home_xi     = result.get("home_xi", [])
    away_xi     = result.get("away_xi", [])

    # ── Header ────────────────────────────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"  {home:^30}  {home_goals} - {away_goals}  {away:^30}")
    print(f"{'─'*80}")

    # ── Goal events ───────────────────────────────────────────────────────────
    home_goal_events = [e for e in events if e["type"] == "goal" and e["team"] == home]
    away_goal_events = [e for e in events if e["type"] == "goal" and e["team"] == away]

    if home_goal_events or away_goal_events:
        print()
        max_rows = max(len(home_goal_events), len(away_goal_events))
        for i in range(max_rows):
            left = right = ""
            if i < len(home_goal_events):
                e = home_goal_events[i]
                assist = f" ({e['assister']})" if e.get("assister") else ""
                left = f"  ⚽ {e['player']}{assist} {e['minute']}'"
                left = left[:48] # Ensure it doesn't exceed the column width
            if i < len(away_goal_events):
                e = away_goal_events[i]
                assist = f" ({e['assister']})" if e.get("assister") else ""
                right = f"⚽ {e['player']}{assist} {e['minute']}'"
            print(f"{left:<50}{right}")
    else:
        print("\n  No goals scored.")

    # ── Lineups ───────────────────────────────────────────────────────────────
    print(f"\n  {'─'*76}")

    position_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    home_sorted = sorted(home_xi, key=lambda p: position_order.get(p["position"], 4))
    away_sorted = sorted(away_xi, key=lambda p: position_order.get(p["position"], 4))

    for i in range(max(len(home_sorted), len(away_sorted))):
        # Home player
        if i < len(home_sorted):
            p    = home_sorted[i]
            name = p["name"]
            g    = sum(1 for e in events if e["type"] == "goal"
                       and e["team"] == home and e["player"] == name)
            a    = sum(1 for e in events if e["type"] == "goal"
                       and e.get("assister") == name)
            yellows  = sum(1 for e in events if e["type"] == "yellow_card"
                        and e["team"] == home and e["player"] == name)
            reds     = sum(1 for e in events if e["type"] == "red_card"
                        and e["team"] == home and e["player"] == name)
            injuries = sum(1 for e in events if e["type"] == "injury"
                        and e["team"] == home and e["player"] == name)
            icons = ("⚽" * g) + ("👟" * a) + ("🟨" * yellows) + ("🟥" * reds) + ("🚑" * injuries)
            rating    = (f"{ratings[name]:.1f}" if name in ratings and ratings[name] is not None else " — ")
            left_name = f"{name} {icons}".strip()
        else:
            left_name, rating = "", ""

        # Away player
        if i < len(away_sorted):
            p      = away_sorted[i]
            a_name = p["name"]
            g      = sum(1 for e in events if e["type"] == "goal"
                         and e["team"] == away and e["player"] == a_name)
            a      = sum(1 for e in events if e["type"] == "goal"
                         and e.get("assister") == a_name)
            a_icons    = ("⚽" * g) + ("👟" * a)
            a_rating   = (f"{ratings[a_name]:.1f}" if a_name in ratings and ratings[a_name] is not None else " — ")
            right_name = f"{a_name} {a_icons}".strip()
        else:
            right_name, a_rating = "", ""

        print(f"  {left_name:<28}{rating:>4}    {a_rating:<4}{right_name}")

    print(f"  {'─'*76}")

    # ── Substitutes (placeholder) ──────────────────────────────────────────
    sub_events = [e for e in events if e["type"] == "substitution"]
    home_subs  = [e for e in sub_events if e["team"] == home]
    away_subs  = [e for e in sub_events if e["team"] == away]
    
    print(f"\n  SUBSTITUTES")
    print(f"  {'─'*36}    {'─'*36}")
    
    max_sub_rows = max(len(home_subs), len(away_subs), 1)
    for i in range(max_sub_rows):
        left = right = "—"
        if i < len(home_subs):
            s = home_subs[i]
            left = f"↑ {s['player_on']}  ↓ {s['player_off']} {s['minute']}'"
        if i < len(away_subs):
            s = away_subs[i]
            right = f"↑ {s['player_on']}  ↓ {s['player_off']} {s['minute']}'"
        print(f"  {left:<38}    {right}")

    # ── Shot stats ────────────────────────────────────────────────────────────
    h_on  = sum(1 for e in events if e["team"] == home and e["type"] == "shot_on_target")
    a_on  = sum(1 for e in events if e["team"] == away and e["type"] == "shot_on_target")
    h_off = sum(1 for e in events if e["team"] == home and e["type"] == "shot_off_target")
    a_off = sum(1 for e in events if e["team"] == away and e["type"] == "shot_off_target")
    
    # ── Defense stats ───────────────────────────────────────────────────────
    h_saves     = sum(1 for e in events if e["team"] == home and e["type"] == "save")
    a_saves     = sum(1 for e in events if e["team"] == away and e["type"] == "save")
    h_tkl_total = sum(1 for e in events if e["team"] == home and e["type"] == "tackle")
    a_tkl_total = sum(1 for e in events if e["team"] == away and e["type"] == "tackle")
    h_tkl_won   = sum(1 for e in events if e["team"] == home and e["type"] == "tackle" and e["success"])
    a_tkl_won   = sum(1 for e in events if e["team"] == away and e["type"] == "tackle" and e["success"])

    print(f"\n  Shots on target:  {h_on} - {a_on}")
    print(f"  Shots off target: {h_off} - {a_off}")
    print(f"  Saves:           {h_saves} - {a_saves}")
    print(f"  Tackles won:       {h_tkl_won} - {a_tkl_won}")
    
    
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
maritima_thesia = Team("Kluba Maritima Thesias", 65, 64, 67)
mercaria = Team("Mercaria Kluba", 63, 67, 65)
portavar = Team("Portavar Kluba", 60, 58, 59)
esalum = Team("Kluba Sportika Esalumou", 51, 53, 52)
mileius = Team("Kluba Sportika Mileiu", 58, 56, 59)
galvonon = Team("Kluba Sportika Galvononos", 66, 68, 63)
pk_galvonon = Team("Populara Kluba Galvononos", 61, 60, 61)
gedium = Team("Kluba Sportika Gedimou", 58, 59, 61)
soleium = Team("Kluba Sportika Soleiu", 57, 60, 58)
metia = Team("Kluba Maritima Metia", 50, 50, 51)
alentum = Team("Kluba Sportika Alentumou", 60, 62, 61)

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
    
start_year = 1896
num_seasons = 3

for i in range(num_seasons):
    season_year = f"{start_year + i}/{str(start_year + i + 1)[-2:]}"
    
    print(f"\n\n{'#'*80}")
    print(f"{'#'*80}")
    print(f"Starting {season_year} season")
    print(f"{'#'*80}")
    print(f"{'#'*80}\n\n")
    
    teams = run_season(season_year, teams)
    
    # Save teams after each season
    save_teams_to_file(teams)
    print(f"{season_year} season completed and teams saved.\n")
    
    # Player development - age up and update abilities
    development_log = []
    for team in teams:
        for player in team.squad:
            old_ca = player.current_ability
            player.start_new_season()
            ca_change = player.current_ability - old_ca
            if abs(ca_change) >= 2:  # Log significant changes
                direction = "📈" if ca_change > 0 else "📉"
                development_log.append(
                f"  {direction} {player.name} ({team.name}): CA {old_ca} → {player.current_ability}"
            )
                
    if development_log:
        print(f"\n{'='*80}")
        print(f"Player Development - Start of {season_year} season")
        print(f"{'='*80}\n")
        for log_entry in development_log:
            print(log_entry)
            
    input("Press Enter to start the next season...")
    
print("\nAll seasons completed. Simulation ended.")