from rng import rng
from match_model import (HOME_BONUS, CHANCES_PER_MATCH, SHOT_ON_TARGET, MORALE_POINTS,
                         MIN_PLAYERS, INJURY_PER_TACKLE, possession_share, goal_probability)
from strength import line_ratings

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

POSITION_SCORING_WEIGHT = {"FWD": 65, "MID": 25, "DEF": 10, "GK": 0}
POSITION_ASSIST_WEIGHT  = {"FWD": 40, "MID": 50, "DEF": 10, "GK": 0}


def _attr(player, name):
    """The attribute if this position has it, otherwise overall ability."""
    return player.attributes.get(name, player.current_ability)

def _player_on_pitch(active, evt):
    pid = event_player_id(evt)
    if pid:
        return next((p for p in active if p.id == pid), None)
    return next((p for p in active if p.name == evt.get("player")), None)


def pick_player_for_chance(starting_xi):
    weights = [POSITION_SCORING_WEIGHT.get(p.position, 0) * _attr(p, "finishing") ** 2 for p in starting_xi]
    if sum(weights) == 0:
        return rng.choice([p for p in starting_xi if p.position != "GK"] or list(starting_xi))
    return rng.choices(starting_xi, weights, k=1)[0]

def pick_assister(starting_xi, scorer):
    if rng.randint(1, 100) <= 30:
        return None
    candidates = [p for p in starting_xi if p is not scorer]
    weights = [POSITION_ASSIST_WEIGHT.get(p.position, 0) * _attr(p, "passing") ** 2
               for p in candidates]
    if sum(weights) == 0:
        return None
    return rng.choices(candidates, weights, k=1)[0]

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
        
        replacement = next((p for p in bench if p.position == player_off.position and not p.is_injured), None)
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
    if rng.random() < INJURY_PER_TACKLE:
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
    
    fit = [p for p in bench if not p.is_injured]
    replacement = (next((p for p in fit if p.position == injured_player.position), None)
                   or next(iter(fit), None))
    
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

class _Side:
    """Everything one team carries through a match (replaces the copy-pasted team1/team2 variables)."""
    def __init__(self, team):
        self.team = team
        self.xi = team.select_starting_xi()
        self.active = list(self.xi)
        self.bench = [p for p in team.squad
                      if p not in self.xi and not (p.is_injured or p.is_suspended or p.is_retired)]
        self.played = list(self.xi)
        self.subs_used = 0
        self.yellows = {}
        self.goals = 0

    def ratings(self):
        bonus = self.team.morale * MORALE_POINTS
        return {line: value + bonus for line, value in line_ratings(self.active).items()}


def _handle_injury(side, evt, entry_minute, exit_minute, max_subs, minute, events):
    injured = _player_on_pitch(side.active, evt)
    if not injured:
        return
    active, bench, sub_events, subs_used = attempt_forced_sub(
        side.team.name, side.active, side.bench, injured, entry_minute, exit_minute,
        side.played, side.subs_used, max_subs, minute)
    if sub_events:
        side.active, side.bench, side.subs_used = active, bench, subs_used
        events.extend(sub_events)
    else:                                   # no substitute possible: play on a man short
        side.active = [p for p in side.active if p.id != injured.id]
        exit_minute[injured.id] = minute


def _play_chance(att, dfn, bonus, minute, events, entry_minute, exit_minute, max_subs, cards_enabled):
    """One attacking chance: a tackle attempt, then (maybe) a goal."""
    tackle_event, modifier = resolve_tackle(dfn.active, dfn.team.name, minute)
    if tackle_event:
        events.append(tackle_event)
        tackler = _player_on_pitch(dfn.active, tackle_event)
        if tackler:
            extra, dfn.yellows = process_tackle_aftermath(
                tackle_event, tackler, att.active, att.team.name, dfn.team.name,
                minute, dfn.yellows, cards_enabled)
            for evt in extra:
                events.append(evt)
                if evt["type"] == "red_card":
                    sent_off = _player_on_pitch(dfn.active, evt)
                    if sent_off:
                        dfn.active = [p for p in dfn.active if p.id != sent_off.id]
                        exit_minute[sent_off.id] = minute
                elif evt["type"] == "injury":
                    side = att if evt["team"] == att.team.name else dfn
                    _handle_injury(side, evt, entry_minute, exit_minute, max_subs, minute, events)

    # ratings are computed AFTER the tackle, so a red card already counts
    edge = att.ratings()["attack"] + bonus - dfn.ratings()["defense"]
    if rng.random() < goal_probability(edge) * modifier:
        scorer = pick_player_for_chance(att.active)
        scorer.goals += 1
        att.goals += 1
        assister = pick_assister(att.active, scorer)
        if assister:
            assister.assists += 1
        events.append({"minute": minute, "team": att.team.name, "type": "goal",
                       **goal_refs(scorer, assister)})
        events.append({"minute": minute, "team": att.team.name, "type": "shot_on_target",
                       **player_ref(scorer)})
    else:
        shooter = pick_player_for_chance(att.active)
        if rng.random() < SHOT_ON_TARGET:
            gk = next((p for p in dfn.active if (p.playing_as or p.position) == "GK"), None)
            if gk:
                events.append({"minute": minute, "team": dfn.team.name, "type": "save",
                               **player_ref(gk)})
            events.append({"minute": minute, "team": att.team.name, "type": "shot_on_target",
                           **player_ref(shooter)})
        else:
            events.append({"minute": minute, "team": att.team.name, "type": "shot_off_target",
                           **player_ref(shooter)})


def simulate_match(team1, team2, max_subs=0, is_home_game=True, season_year="1896/97"):
    from rules import get_card_rules
    cards_enabled = get_card_rules(season_year)

    home, away = _Side(team1), _Side(team2)
    sides = (home, away)
    
    # if not enough players to start, the match is forfeited
    short = [s for s in sides if len(s.xi) < MIN_PLAYERS]
    if short:
        loser = min(short, key=lambda s: len(s.xi))
        winner = away if loser is home else home
        events = [{"minute": 0, "team": loser.team.name, "type": "forfeit",
                   "reason": f"only {len(loser.xi)} players available"}]
        hg, ag = (3, 0) if winner is home else (0, 3)
        return hg, ag, events, {}, [], []
    
    for side in sides:
        for p in side.xi:
            p.appearances += 1            

    entry_minute = {p.id: 0 for s in sides for p in s.xi}
    exit_minute = {p.id: 90 for s in sides for p in s.xi}
    events = []
    checked_windows = set()
    home_bonus = HOME_BONUS if is_home_game else 0.0

    total_chances = CHANCES_PER_MATCH + rng.randint(-5, 5)
    chance_minutes = sorted(rng.randint(1, 90) for _ in range(total_chances))
    
    abandoned = None

    for minute in chance_minutes:
        # ── substitution windows ──────────────────────────────────────────────
        if max_subs > 0:
            for window in SUB_WINDOWS:
                if minute > window and window not in checked_windows:
                    checked_windows.add(window)
                    for side, other in ((home, away), (away, home)):
                        side.active, side.bench, sub_events, side.subs_used = attempt_substitutions(
                            side.team.name, side.active, side.bench, events,
                            other.goals, side.subs_used, max_subs, window)
                        for evt in sub_events:
                            events.append(evt)
                            on_id, off_id = sub_on_id(evt), sub_off_id(evt)
                            entry_minute[on_id] = window
                            exit_minute[off_id] = window
                            sub = next((p for p in side.team.squad if p.id == on_id), None)
                            if sub:
                                side.played.append(sub)

        # ── who has the ball? decided by the midfield gap ─────────────────────
        r_home, r_away = home.ratings(), away.ratings()
        share = possession_share(r_home["midfield"] + home_bonus, r_away["midfield"])
        if rng.random() < share:
            att, dfn, bonus = home, away, home_bonus
        else:
            att, dfn, bonus = away, home, 0.0
        _play_chance(att, dfn, bonus, minute, events,
                     entry_minute, exit_minute, max_subs, cards_enabled)
        abandoned = next((s for s in sides if len(s.active) < MIN_PLAYERS), None)
        if abandoned:
            break
        
    if abandoned:
        winner = away if abandoned is home else home
        winner.goals = max(winner.goals, abandoned.goals + 3)
        events.append({"minute": minute, "team": abandoned.team.name, "type": "forfeit",
                       "reason": "fewer than 7 players remaining on the pitch"})

    # ── clean sheets (the starting keeper gets the credit) ────────────────────
    for side, other in ((home, away), (away, home)):
        if other.goals == 0:
            gk = next((p for p in side.xi if (p.playing_as or p.position) == "GK"), None)
            if gk:
                gk.clean_sheets += 1

    # ── ratings ───────────────────────────────────────────────────────────────
    ratings = {}

    def compute_ratings(side, goals_conceded):
        team_name = side.team.name
        for player in side.played:
            minutes = exit_minute.get(player.id, 90) - entry_minute.get(player.id, 0)
            p_goals = sum(1 for e in events
                          if e["type"] == "goal" and e["team"] == team_name
                          and event_player_matches(e, player))
            p_assists = sum(1 for e in events
                            if e["type"] == "goal" and e["team"] == team_name
                            and event_assister_matches(e, player))
            if minutes < 10 and p_goals == 0 and p_assists == 0:
                ratings[player.id] = None
                continue
            p_saves = sum(1 for e in events
                          if e["type"] == "save" and event_player_matches(e, player))
            p_tackles_won = sum(1 for e in events
                                if e["type"] == "tackle" and event_player_matches(e, player)
                                and e["success"])
            p_tackles_attempted = sum(1 for e in events
                                      if e["type"] == "tackle" and event_player_matches(e, player))
            rating = calculate_match_rating(
                player, p_goals, p_assists,
                clean_sheet=(goals_conceded == 0), goals_conceded=goals_conceded,
                saves=p_saves, tackles_won=p_tackles_won, tackles_attempted=p_tackles_attempted)
            player.update_season_rating(rating)
            ratings[player.id] = rating

    compute_ratings(home, away.goals)
    compute_ratings(away, home.goals)
    return home.goals, away.goals, events, ratings, home.xi, away.xi

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