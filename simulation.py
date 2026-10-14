from rng import rng

from player_refs import (
    event_assister_matches,
    event_player_id,
    event_player_matches,
    goal_refs,
    player_ref,
    sub_refs,
    sub_off_id,
    sub_on_id,
)


def _player_on_pitch(active, evt):
    pid = event_player_id(evt)
    if pid:
        return next((p for p in active if p.id == pid), None)
    return next((p for p in active if p.name == evt.get("player")), None)


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
        
    if not weighted_players:
        weighted_players = [p for p in starting_xi if p.position != "GK"]  # Fallback to any outfield player if something goes wrong
        
    if not weighted_players:
        return rng.choice(starting_xi)  # Last resort, pick any player

    return rng.choice(weighted_players)

def pick_assister(starting_xi, scorer):
    """Pick a player to credit with an assist (70% chance of assist)"""
    roll = rng.randint(1, 100)
    
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
        weighted_players = [p for p in starting_xi if p != scorer and p.position != "GK"]
    
    if not weighted_players:
        return None

    chosen = rng.choice(weighted_players)
    return chosen

def resolve_tackle(defending_xi, defending_team_name, minute):
    # 35% chance a tackle is attempted at any given minute (add foul events later)
    if rng.random() > 0.35:
        return None, 1.0  # No tackle, no change to chances
    
    candidates = []
    for p in defending_xi:
        if p.position == "DEF":
            candidates.extend([p] * 3)
        elif p.position == "MID":
            candidates.extend([p] * 2)
            
    if not candidates:
        return None, 1.0  # No defenders or midfielders available, no change to chances
    
    tackler = rng.choice(candidates)
    tackling = tackler.attributes.get("tackling", tackler.current_ability)
    
    success_chance = max(25, min(65, 30 + (tackling / 5)))
    success = rng.randint(1, 100) < success_chance
    
    event = {
        "minute": minute,
        "team": defending_team_name,
        "type": "tackle",
        **player_ref(tackler),
        "success": success,
    }
    
    return event, 0.55 if success else 1.0 # Reduce chances if tackle fails

SUB_THRESHOLD = 5.5
SUB_WINDOWS = [45, 60, 75, 85]

def estimate_current_rating(player, team_name, events, goals_conceded):
    # Simplified rating used for substitution decisions mid-match
    goal_bonus      = {"GK": 1.5, "DEF": 1.3, "MID": 1.2, "FWD": 1.0}
    assist_bonus    = {"GK": 1.2, "DEF": 1.0, "MID": 0.9, "FWD": 0.8}
    
    p_goals = sum(
        1 for e in events
        if e["type"] == "goal" and e["team"] == team_name and event_player_matches(e, player)
    )
    p_assists = sum(
        1 for e in events
        if e["type"] == "goal" and e["team"] == team_name and event_assister_matches(e, player)
    )
    
    rating = 6.0
    rating += p_goals   * goal_bonus.get(player.position, 1.0)
    rating += p_assists * assist_bonus.get(player.position, 0.8)
    
    if player.position == "GK":
        rating -= goals_conceded * 0.3  # Penalty for goals conceded for keepers
    elif player.position == "DEF":
        rating -= goals_conceded * 0.2  # Small penalty for defenders if team concedes
        
    return rating

def attempt_substitutions(team_name, active_xi, bench, events, goals_conceded,
                          subs_used, max_subs, minute):
    # Attempt performance-based substitutions at a given window
    sub_events = []
    
    if subs_used >= max_subs or not bench:
        return active_xi, bench, sub_events, subs_used
    
    outfield = [p for p in active_xi if p.position != "GK"]
    rated    = [(p, estimate_current_rating(p, team_name, events, goals_conceded)) for p in outfield]
    rated.sort(key=lambda x: x[1])
    
    for player_off, rating, in rated:
        if subs_used >= max_subs:
            break
        if rating >= SUB_THRESHOLD:
            break
        
        replacement = next((p for p in bench if p.position == player_off.position), None)
        if not replacement:
            continue
        
        active_xi   = [replacement if p == player_off else p for p in active_xi]
        bench       = [p for p in bench if p != replacement]
        bench.append(player_off)
        
        replacement.appearances += 1
        
        sub_events.append({
            "minute": minute,
            "team": team_name,
            "type": "substitution",
            **sub_refs(player_off, replacement),
            "position": player_off.position,
        })
        subs_used += 1
        
    return active_xi, bench, sub_events, subs_used

INJURY_TIERS = [
    ("minor",       1,  2,  0.50),
    ("moderate",    3,  6,  0.30),
    ("severe",      7,  15, 0.15),
    ("critical",    20, 45, 0.05)
]

def roll_injury_severity():
    roll = rng.random()
    cumulative = 0.0
    for severity, min_m, max_m, weight in INJURY_TIERS:
        cumulative += weight
        if roll <= cumulative:
            return severity, rng.randint(min_m, max_m)
    return "minor", 1
    
def process_tackle_aftermath(tackle_event, tackler, attacking_active, attacking_team_name,
                             defending_team_name, minute, in_match_yellows, cards_enabled):
    """
    After a tackle, check for fouls, cards and injuries.
    Returns (extra_events, updated_in_match_yellows)
    """
    extra_events = []
    
    # Foul check
    foul_chance = 0.05 if tackle_event["success"] else 0.20
    if rng.random() < foul_chance:
        extra_events.append({
            "minute": minute,
            "team": defending_team_name,
            "type": "foul",
            **player_ref(tackler),
        })
        
        if cards_enabled:
            card_roll = rng.random()
            if card_roll < 0.05:
                # Direct red card
                extra_events.append({
                    "minute": minute,
                    "team": defending_team_name,
                    "type": "red_card",
                    **player_ref(tackler),
                    "reason": "violent tackle",
                })
                tackler.red_cards += 1
                tackler.is_suspended = True
                tackler.suspension_matches_left = 3
            elif card_roll < 0.30:
                in_match_yellows[tackler.id] = in_match_yellows.get(tackler.id, 0) + 1
                
                extra_events.append({
                    "minute": minute,
                    "team": defending_team_name,
                    "type": "yellow_card",
                    **player_ref(tackler),
                })
                
                if in_match_yellows[tackler.id] >= 2:
                    # Second yellow card --> direct red card
                    extra_events.append({
                        "minute": minute,
                        "team": defending_team_name,
                        "type": "red_card",
                        **player_ref(tackler),
                        "reason": "second_yellow",
                    })
                    tackler.red_cards += 1
                    tackler.is_suspended = True
                    tackler.suspension_matches_left = 1
                    
    # Injury check (independent or foul)
    if rng.random() < 0.03:
        # 70/30 - attacker or tackler gets hurt
        if rng.random() < 0.7 and attacking_active:
            candidates = [p for p in attacking_active if p.position != "GK"]
            injured = rng.choice(candidates) if candidates else None
            inj_team = attacking_team_name
        else:
            injured = tackler
            inj_team = defending_team_name
            
        if injured and not injured.is_injured:
            severity, matches_out = roll_injury_severity()
            injured.is_injured = True
            injured.injury_severity = severity
            injured.injury_matches_left = matches_out
            injured.career_injuries += 1
            extra_events.append({
                "minute": minute,
                "team": inj_team,
                "type": "injury",
                **player_ref(injured),
                "severity": severity,
                "matches_out": matches_out,
            })
            
    return extra_events, in_match_yellows

def attempt_forced_sub(team_name, active_xi, bench, injured_player, entry_minute,
                       exit_minute, played, subs_used, max_subs, minute):
    """
    Forced substitution for an injured player, uses one sub allocation.
    """
    sub_events = []
    if not bench or max_subs == 0 or subs_used >= max_subs:
        return active_xi, bench, sub_events, subs_used
    
    replacement = (next((p for p in bench if p.position == injured_player.position), None)
                   or next(iter(bench), None))
    
    if not replacement:
        return active_xi, bench, sub_events, subs_used
    
    exit_minute[injured_player.id] = minute
    active_xi = [replacement if p == injured_player else p for p in active_xi]
    bench = [p for p in bench if p != replacement]
    bench.append(injured_player)
    
    replacement.appearances += 1
    entry_minute[replacement.id] = minute
    played.append(replacement)
    subs_used += 1
    
    sub_events.append({
        "minute": minute,
        "team": team_name,
        "type": "substitution",
        **sub_refs(injured_player, replacement),
        "position": injured_player.position,
        "reason": "injury",
    })
    return active_xi, bench, sub_events, subs_used

def _handle_injury_event(evt, team1, team2,
                         t1_active, t1_bench, t1_played,
                         t2_active, t2_bench, t2_played,
                         entry_minute, exit_minute,
                         t1_subs_used, t2_subs_used,
                         max_subs, minute, events):
    if evt["team"] == team1.name:
        obj = _player_on_pitch(t1_active, evt)
        if obj:
            t1_active[:] = [p for p in t1_active if p.id != obj.id]
            exit_minute[obj.id] = minute
            t1_active[:], t1_bench[:], sub_evts, t1_subs_used = attempt_forced_sub(
                team1.name, t1_active, t1_bench, obj,
                entry_minute, exit_minute, t1_played,
                t1_subs_used, max_subs, minute
            )
            for s in sub_evts:
                events.append(s)
    else:
        obj = _player_on_pitch(t2_active, evt)
        if obj:
            t2_active[:] = [p for p in t2_active if p.id != obj.id]
            exit_minute[obj.id] = minute
            t2_active[:], t2_bench[:], sub_evts, t2_subs_used = attempt_forced_sub(
                team2.name, t2_active, t2_bench, obj,
                entry_minute, exit_minute, t2_played,
                t2_subs_used, max_subs, minute
            )
            for s in sub_evts:
                events.append(s)

    return t1_subs_used, t2_subs_used

def simulate_match(team1, team2, max_subs=0, is_home_game=True, season_year="1896/97"):
    team1_xi = team1.select_starting_xi(opponent_strength=team2.get_strength())
    team2_xi = team2.select_starting_xi(opponent_strength=team1.get_strength())

    if not team1_xi:
        raise ValueError(f"{team1.name} has no players available for the match!")
    if not team2_xi:
        raise ValueError(f"{team2.name} has no players available for the match!")

    # Active XIs change with subs; originals kept for display and clean sheets
    team1_active = list(team1_xi)
    team2_active = list(team2_xi)
    team1_bench  = [p for p in team1.squad if p not in team1_xi]
    team2_bench  = [p for p in team2.squad if p not in team2_xi]

    team1_subs_used = 0
    team2_subs_used = 0

    # Track when each player entered and left the pitch
    entry_minute = {p.id: 0 for p in team1_xi + team2_xi}
    exit_minute = {p.id: 90 for p in team1_xi + team2_xi}
    
    from rules import get_card_rules
    cards_enabled = get_card_rules(season_year)
    team1_in_match_yellows = {}
    team2_in_match_yellows = {}

    # All players who actually played (grows as subs come on)
    team1_played = list(team1_xi)
    team2_played = list(team2_xi)

    for player in team1_xi:
        player.appearances += 1
    for player in team2_xi:
        player.appearances += 1

    if is_home_game:
        home_boost = 2
    else:
        home_boost = 0

    base_chances  = 32
    midfield_bonus = ((team1.midfield + home_boost) + team2.midfield) / 20
    total_chances  = base_chances + midfield_bonus + rng.randint(-5, 5)

    chance_minutes = sorted([rng.randint(1, 90) for _ in range(int(total_chances))])

    events      = []
    team1_goals = 0
    team2_goals = 0
    checked_windows = set()

    for current_minute in chance_minutes:

        # ── Substitution windows ──────────────────────────────────────────────
        if max_subs > 0:
            for window in SUB_WINDOWS:
                if current_minute > window and window not in checked_windows:
                    t1_conceded = sum(1 for e in events if e["type"] == "goal"
                                      and e["team"] == team2.name)
                    t2_conceded = sum(1 for e in events if e["type"] == "goal"
                                      and e["team"] == team1.name)

                    team1_active, team1_bench, evts1, team1_subs_used = attempt_substitutions(
                        team1.name, team1_active, team1_bench, events,
                        t1_conceded, team1_subs_used, max_subs, window
                    )
                    for evt in evts1:
                        events.append(evt)
                        on_id = sub_on_id(evt)
                        off_id = sub_off_id(evt)
                        if on_id:
                            entry_minute[on_id] = window
                        if off_id:
                            exit_minute[off_id] = window
                        sub = next((p for p in team1.squad if p.id == on_id), None) if on_id else None
                        if sub:
                            team1_played.append(sub)

                    team2_active, team2_bench, evts2, team2_subs_used = attempt_substitutions(
                        team2.name, team2_active, team2_bench, events,
                        t2_conceded, team2_subs_used, max_subs, window
                    )
                    for evt in evts2:
                        events.append(evt)
                        on_id = sub_on_id(evt)
                        off_id = sub_off_id(evt)
                        if on_id:
                            entry_minute[on_id] = window
                        if off_id:
                            exit_minute[off_id] = window
                        sub = next((p for p in team2.squad if p.id == on_id), None) if on_id else None
                        if sub:
                            team2_played.append(sub)

                    checked_windows.add(window)

        # ── Chance resolution — use active_xi throughout ──────────────────────
        team1_midfield_power = (team1.midfield + home_boost) ** 4
        team2_midfield_power = team2.midfield ** 4
        total_power  = team1_midfield_power + team2_midfield_power
        team1_chance = team1_midfield_power / total_power

        if rng.random() < team1_chance:
            tackle_event, chance_modifier = resolve_tackle(team2_active, team2.name, current_minute)
            if tackle_event:
                events.append(tackle_event)
                tackler = _player_on_pitch(team2_active, tackle_event)
                if tackler:
                    extra, team2_in_match_yellows = process_tackle_aftermath(
                        tackle_event, tackler, team1_active,
                        team1.name, team2.name,
                        current_minute, team2_in_match_yellows, cards_enabled
                    )
                    for evt in extra:
                        events.append(evt)
                        if evt["type"] == "red_card":
                            sent_off = _player_on_pitch(team2_active, evt)
                            if sent_off:
                                team2_active = [p for p in team2_active if p.id != sent_off.id]
                        elif evt["type"] == "injury":
                            team1_subs_used, team2_subs_used = _handle_injury_event(evt, team1, team2,
                                                                team1_active, team1_bench, team1_played,
                                                                team2_active, team2_bench, team2_played,
                                                                entry_minute, exit_minute,
                                                                team1_subs_used, team2_subs_used,
                                                                max_subs, current_minute, events)

            shot_quality    = (team1.attack + home_boost) - team2.defense
            scoring_chance  = max(8, min(shot_quality / 2, 40))
            scoring_chance  = min(scoring_chance + team1.attack / 30, 45) * chance_modifier
            if len(team1_active) < 11:
                scoring_chance *= len(team1_active) / 11

            if rng.randint(1, 100) < scoring_chance:
                team1_goals += 1
                scorer   = pick_player_for_chance(team1_active)
                scorer.goals += 1
                assister = pick_assister(team1_active, scorer)
                if assister:
                    assister.assists += 1
                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": "goal",
                    **goal_refs(scorer, assister),
                })
                events.append({
                    "minute": current_minute,
                    "team": team1.name,
                    "type": "shot_on_target",
                    **player_ref(scorer),
                })
            else:
                shooter  = pick_player_for_chance(team1_active)
                accuracy = 20 + (team1.attack / 5)
                if rng.randint(1, 100) < accuracy:
                    gk = next((p for p in team2_active if p.position == "GK"), None)
                    if gk:
                        events.append({
                            "minute": current_minute,
                            "team": team2.name,
                            "type": "save",
                            **player_ref(gk),
                        })
                    events.append({
                        "minute": current_minute,
                        "team": team1.name,
                        "type": "shot_on_target",
                        **player_ref(shooter),
                    })
                else:
                    events.append({
                        "minute": current_minute,
                        "team": team1.name,
                        "type": "shot_off_target",
                        **player_ref(shooter),
                    })
        else:
            tackle_event, chance_modifier = resolve_tackle(team1_active, team1.name, current_minute)
            if tackle_event:
                events.append(tackle_event)
                tackler = _player_on_pitch(team1_active, tackle_event)
                if tackler:
                    extra, team1_in_match_yellows = process_tackle_aftermath(
                        tackle_event, tackler, team2_active,
                        team2.name, team1.name,
                        current_minute, team1_in_match_yellows, cards_enabled
                    )
                    for evt in extra:
                        events.append(evt)
                        if evt["type"] == "red_card":
                            sent_off = _player_on_pitch(team1_active, evt)
                            if sent_off:
                                team1_active = [p for p in team1_active if p.id != sent_off.id]
                        elif evt["type"] == "injury":
                            team1_subs_used, team2_subs_used = _handle_injury_event(evt, team1, team2,
                                team1_active, team1_bench, team1_played,
                                team2_active, team2_bench, team2_played,
                                entry_minute, exit_minute,
                                team1_subs_used, team2_subs_used,
                                max_subs, current_minute, events)

            shot_quality   = team2.attack - team1.defense
            scoring_chance = max(8, min(shot_quality / 2, 40))
            scoring_chance = min(scoring_chance + team2.attack / 30, 45) * chance_modifier
            if len(team2_active) < 11:
                scoring_chance *= len(team2_active) / 11

            if rng.randint(1, 100) < scoring_chance:
                team2_goals += 1
                scorer   = pick_player_for_chance(team2_active)
                scorer.goals += 1
                assister = pick_assister(team2_active, scorer)
                if assister:
                    assister.assists += 1
                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": "goal",
                    **goal_refs(scorer, assister),
                })
                events.append({
                    "minute": current_minute,
                    "team": team2.name,
                    "type": "shot_on_target",
                    **player_ref(scorer),
                })
            else:
                shooter  = pick_player_for_chance(team2_active)
                accuracy = 20 + (team2.attack / 5)
                if rng.randint(1, 100) < accuracy:
                    gk = next((p for p in team1_active if p.position == "GK"), None)
                    if gk:
                        events.append({
                            "minute": current_minute,
                            "team": team1.name,
                            "type": "save",
                            **player_ref(gk),
                        })
                    events.append({
                        "minute": current_minute,
                        "team": team2.name,
                        "type": "shot_on_target",
                        **player_ref(shooter),
                    })
                else:
                    events.append({
                        "minute": current_minute,
                        "team": team2.name,
                        "type": "shot_off_target",
                        **player_ref(shooter),
                    })

    # ── Clean sheets (use original XI — the starting GK gets the credit) ──────
    if team2_goals == 0:
        gk = next((p for p in team1_xi if p.position == "GK"), None)
        if gk:
            gk.clean_sheets += 1
    if team1_goals == 0:
        gk = next((p for p in team2_xi if p.position == "GK"), None)
        if gk:
            gk.clean_sheets += 1

    # ── Ratings (all players who participated, with minutes check) ────────────
    ratings = {}

    def compute_ratings(played, team_name, goals_conceded):
        for player in played:
            minutes = exit_minute.get(player.id, 90) - entry_minute.get(player.id, 0)
            p_goals = sum(
                1 for e in events
                if e["type"] == "goal" and e["team"] == team_name and event_player_matches(e, player)
            )
            p_assists = sum(
                1 for e in events
                if e["type"] == "goal" and e["team"] == team_name and event_assister_matches(e, player)
            )

            if minutes < 10 and p_goals == 0 and p_assists == 0:
                ratings[player.id] = None
                continue

            p_saves = sum(
                1 for e in events
                if e["type"] == "save" and event_player_matches(e, player)
            )
            p_tackles_won = sum(
                1 for e in events
                if e["type"] == "tackle" and event_player_matches(e, player) and e["success"]
            )
            p_tackles_attempted = sum(
                1 for e in events
                if e["type"] == "tackle" and event_player_matches(e, player)
            )

            rating = calculate_match_rating(
                player, p_goals, p_assists,
                clean_sheet=(goals_conceded == 0),
                goals_conceded=goals_conceded,
                saves=p_saves,
                tackles_won=p_tackles_won,
                tackles_attempted=p_tackles_attempted
            )
            player.update_season_rating(rating)
            ratings[player.id] = rating

    compute_ratings(team1_played, team1.name, team2_goals)
    compute_ratings(team2_played, team2.name, team1_goals)

    return team1_goals, team2_goals, events, ratings, team1_xi, team2_xi

def calculate_match_rating(player, player_goals, player_assists, clean_sheet, goals_conceded, 
                           saves=0, tackles_won=0, tackles_attempted=0):
    # Simple rating calculation based on goals, assists, clean sheets, and goals conceded
    rating = 6.0  # Base rating
    
    goal_bonus      = {"GK": 1.5, "DEF": 1.3, "MID": 1.2, "FWD": 1.0}
    assist_bonus    = {"GK": 1.2, "DEF": 1.0, "MID": 0.9, "FWD": 0.8}
    cs_bonus        = {"GK": 1.0, "DEF": 0.7, "MID": 0.2, "FWD": 0.0}
    
    rating += player_goals * goal_bonus.get(player.position, 0.8)
    rating += player_assists * assist_bonus.get(player.position, 0.6)
    
    if clean_sheet:
        rating += cs_bonus.get(player.position, 0.0)
        
    if player.position == "GK":
        rating -= goals_conceded * 0.3  # Penalty for goals conceded for keepers
        rating += min(saves * 0.15, 1.2)  # Bonus for saves, capped to prevent overrating
    elif player.position == "DEF":
        rating -= goals_conceded * 0.2  # Small penalty for defenders if team concedes
        rating += tackles_won * 0.15  # Bonus for successful tackles
        rating -= (tackles_attempted - tackles_won) * 0.05  # Small penalty for failed tackles
    elif player.position == "MID":
        rating += tackles_won * 0.1  # Bonus for successful tackles
        rating -= (tackles_attempted - tackles_won) * 0.05  # Small penalty for failed tackles
        
    return round(max(4.0, min(9.5, rating)), 1)  # Clamp rating between 4.0 and 9.5