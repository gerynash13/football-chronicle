import random

class Team:
    def __init__(self, name, attack, midfield, defense):
        self.name = name
        self.attack = attack
        self.midfield = midfield
        self.defense = defense

barcelona = Team("FC Barcelona", 85, 83, 78)
real_madrid = Team("Real Madrid CF", 83, 74, 80)
girona = Team("Girona FC", 72, 68, 70)

def simulate_match(team1, team2):
    base_chances = 28
    midfield_bonus = (team1.midfield + team2.midfield) / 20
    total_chances = base_chances + midfield_bonus + random.randint(-5, 5)

    # Generate random minutes and put them in order
    chance_minutes = [random.randint(1, 90) for _ in range(int(total_chances))]
    chance_minutes.sort()

    events = []
    team1_goals = 0
    team2_goals = 0

    for current_minute in chance_minutes:
        team1_midfield_power = team1.midfield ** 3
        team2_midfield_power = team2.midfield ** 3
        total_power = team1_midfield_power + team2_midfield_power
        team1_chance = team1_midfield_power / total_power

        if random.random() < team1_chance:
            shot_quality = team1.attack - team2.defense
            scoring_chance = max(5, min(shot_quality / 4, 25))
            team_quality_bonus = team1.attack / 40
            scoring_chance = min(scoring_chance + team_quality_bonus, 28)

            if random.randint(1, 100) < scoring_chance:
                team1_goals += 1
                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": "goal",
                    "player": None
                })

            else:
                # Give accuracy depending on the team level
                accuracy = 20 + (team1.attack / 5)

                if random.randint(1, 100) < accuracy:
                    event_type = "shot_on_target"
                else:
                    event_type = "shot_off_target"

                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": event_type,
                    "player": None
                })

        else:
            shot_quality = team2.attack - team1.defense
            scoring_chance = max(5, min(shot_quality /4, 25))
            team_quality_bonus = team2.attack / 40
            scoring_chance = min(scoring_chance + team_quality_bonus, 28)

            if random.randint(1, 100) < scoring_chance:
                team2_goals += 1
                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": "goal",
                    "player": None
                })

            else:
                # Give accuracy depending on the team level
                accuracy = 20 + (team2.attack / 5)

                if random.randint(1, 100) < accuracy:
                    event_type = "shot_on_target"
                else:
                    event_type = "shot_off_target"

                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": event_type,
                    "player": None
                })

    for event in events:
        if event['type'] == "goal":
            print(f"{event['minute']}' - GOAL! {event['team']} scores!")

    team1_shots_on = sum(1 for e in events if e['team'] == team1.name and e['type'] == "shot_on_target")
    team1_shots_off = sum(1 for e in events if e['team'] == team1.name and e['type'] == "shot_off_target")

    team2_shots_on = sum(1 for e in events if e['team'] == team2.name and e['type'] == "shot_on_target")
    team2_shots_off = sum(1 for e in events if e['team'] == team2.name and e['type'] == "shot_off_target")

    print(f"\n{team1.name} Stats:\nShots on target: {team1_shots_on}\nShots off target: {team1_shots_off}\n")        
    print(f"{team2.name} Stats:\nShots on target: {team2_shots_on}\nShots off target: {team2_shots_off}\n")
    
    
    return team1_goals, team2_goals


barcelona_goals, girona_goals = simulate_match(barcelona, girona)

print(f"{barcelona.name} {barcelona_goals} - {girona_goals} {girona.name}")