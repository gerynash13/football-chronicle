import random

class Team:
    def __init__(self, name, attack, midfield, defense):
        self.name = name
        self.attack = attack
        self.midfield = midfield
        self.defense = defense

barcelona = Team("FC Barcelona", 85, 83, 78)
real_madrid = Team("Real Madrid CF", 83, 74, 80)
girona = Team("Girona FC", 50, 46, 49)

def simulate_match(team1, team2):
    base_chances = 28
    midfield_bonus = (team1.midfield + team2.midfield) / 20
    total_chances = base_chances + midfield_bonus + random.randint(-5, 5)

    team1_goals = 0
    team2_goals = 0

    for i in range(int(total_chances)):
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

        else:
            shot_quality = team2.attack - team1.defense
            scoring_chance = max(5, min(shot_quality /4, 25))
            team_quality_bonus = team2.attack / 40
            scoring_chance = min(scoring_chance + team_quality_bonus, 28)
            if random.randint(1, 100) < scoring_chance:
                team2_goals += 1

    return team1_goals, team2_goals


barcelona_goals, girona_goals = simulate_match(barcelona, girona)

print(f"{barcelona.name} {barcelona_goals} - {girona_goals} {girona.name}")