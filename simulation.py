import random

def pick_player_for_chance(starting_xi):
    """Pick a player from the team's squad weighted by position"""
    position_weights = {
        "FWD": 65,
        "MID": 25,
        "DEF": 10,
        "GK": 0
    }

    # Filter players by position and create weighted list
    weighted_players = []
    for player in starting_xi:
        weight = position_weights.get(player.position, 0)
        weighted_players.extend([player] * weight)

    return random.choice(weighted_players)

def pick_assister(starting_xi, scorer):
    """Pick a player to credit with an assist (70% chance of assist)"""
    roll = random.randint(1, 100)
    
    # 30% chance no assist
    if roll <= 30:
        return None
    
    # 70% chance - pick an assister
    position_weights = {
        "FWD": 40,
        "MID": 50,
        "DEF": 10,
        "GK": 0
    }

    weighted_players = []
    for player in starting_xi:
        if player != scorer:
            weight = position_weights.get(player.position, 0)
            weighted_players.extend([player] * weight)
    
    if not weighted_players:
        return None

    chosen = random.choice(weighted_players)
    return chosen

def simulate_match(team1, team2, is_home_game=True):
    # Select starting XI
    team1_xi = team1.select_starting_xi(opponent_strength=team2.get_strength())
    team2_xi = team2.select_starting_xi(opponent_strength=team1.get_strength())

    for player in team1_xi:
        player.appearances += 1
    for player in team2_xi:
        player.appearances += 1
    
    if is_home_game:
        home_boost = 2
    else:
        home_boost = 0

    base_chances = 32
    midfield_bonus = ((team1.midfield + home_boost) + team2.midfield) / 20
    total_chances = base_chances + midfield_bonus + random.randint(-5, 5)

    # Generate random minutes and put them in order
    chance_minutes = [random.randint(1, 90) for _ in range(int(total_chances))]
    chance_minutes.sort()

    events = []
    team1_goals = 0
    team2_goals = 0

    for current_minute in chance_minutes:
        team1_midfield_power = (team1.midfield + home_boost) ** 4
        team2_midfield_power = team2.midfield ** 4
        total_power = team1_midfield_power + team2_midfield_power
        team1_chance = team1_midfield_power / total_power

        if random.random() < team1_chance:
            shot_quality = (team1.attack + home_boost) - team2.defense
            scoring_chance = max(8, min(shot_quality / 2, 40))
            team_quality_bonus = team1.attack / 30
            scoring_chance = min(scoring_chance + team_quality_bonus, 45)

            if random.randint(1, 100) < scoring_chance:
                team1_goals += 1
                scorer = pick_player_for_chance(team1_xi)
                scorer.goals += 1

                assister = pick_assister(team1_xi, scorer)
                if assister:
                    assister.assists += 1

                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": "goal",
                    "player": scorer.name,
                    "assister": assister.name if assister else None
                })
                
                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": "shot_on_target",
                    "player": scorer.name
                })

            else:
                shooter = pick_player_for_chance(team1_xi)

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
                    "player": shooter.name
                })

        else:
            shot_quality = team2.attack - team1.defense
            scoring_chance = max(8, min(shot_quality /2, 40))
            team_quality_bonus = team2.attack / 30
            scoring_chance = min(scoring_chance + team_quality_bonus, 45)

            if random.randint(1, 100) < scoring_chance:
                team2_goals += 1
                scorer = pick_player_for_chance(team2_xi)
                scorer.goals += 1

                assister = pick_assister(team2_xi, scorer)
                if assister:
                    assister.assists += 1

                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": "goal",
                    "player": scorer.name,
                    "assister": assister.name if assister else None
                })
                
                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": "shot_on_target",
                    "player": scorer.name
                })

            else:
                shooter = pick_player_for_chance(team2_xi)

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
                    "player": shooter.name
                })

    team1_shots_on = sum(1 for e in events if e['team'] == team1.name and e['type'] == "shot_on_target")
    team1_shots_off = sum(1 for e in events if e['team'] == team1.name and e['type'] == "shot_off_target")

    team2_shots_on = sum(1 for e in events if e['team'] == team2.name and e['type'] == "shot_on_target")
    team2_shots_off = sum(1 for e in events if e['team'] == team2.name and e['type'] == "shot_off_target")
    
    return team1_goals, team2_goals, events