"""Retirement, academy intake and promotion: what keeps the world alive between seasons."""
from rng import rng
from name_generator import generate_youth

TARGET_SQUAD = {"GK": 2, "DEF": 4, "MID": 4, "FWD": 6}
MAX_SQUAD = 20
MIN_PROMOTION_AGE = 17
MAX_YOUTH_AGE = 20        # Promote or release youth players at this age
MAX_YOUTH = 24

YOUTH_PA_ANCHOR = 70        # Centre of academy potential for an average club
CLUB_WEIGHT = 0.3           # Weight of club culture in youth selection
YOUTH_FACILITY_POINTS = 12  # youth facilities 100 = +12 potential, 0 = -12 potential

def _top_level(players):
    cas = sorted((p.current_ability for p in players if not p.is_retired), reverse=True)[:11]
    return sum(cas) / len(cas) if cas else 40.0

def league_level(teams):
    return sum(_top_level(t.squad) for t in teams) / len(teams)

def retire_players(team, season_label):
    gone = [p for p in team.squad if p.is_retired]
    for p in gone:
        p.retired_season = season_label
    team.squad = [p for p in team.squad if not p.is_retired]
    team.retired.extend(gone)
    return gone

# ACADEMY

def intake_size(team):
    return 3 + round(team.facilities["youth_recruitment"] / 25)   # 3 to 7 player for now

def youth_pa_centre(team, league_lvl):
    club_edge = CLUB_WEIGHT * (_top_level(team.squad) - league_lvl)
    facility = YOUTH_FACILITY_POINTS * (team.facilities["youth"] - 50) / 50
    return YOUTH_PA_ANCHOR + club_edge + facility

def _pick_position(team):
    weights = []
    for position, target in TARGET_SQUAD.items():
        have = sum(1 for p in team.squad + team.youth if p.position == position)
        weights.append(target * (3 if have < target else 1))
    return rng.choices(list(TARGET_SQUAD), weights=weights, k=1)[0]

def _new_youth(team, nation_config, centre, ref_year, age=None):
    wonder_mult = 0.5 + team.facilities["youth_recruitment"] / 100
    return generate_youth(_pick_position(team), centre, team.nation_id, nation_config,
                          ref_year, team.home_region,
                          wonderkid_multiplier=wonder_mult, age=age)
    
def youth_intake(team, nation_config, league_lvl, ref_year, age=None):
    """New academy players for the coming season. They go to the youth team."""
    ref_year = int(ref_year.split("/")[0])
    centre = youth_pa_centre(team, league_lvl)
    arrivals = []
    for _ in range(intake_size(team)):
        youth = _new_youth(team, nation_config, centre, ref_year)
        team.youth.append(youth)
        arrivals.append(youth)
    return arrivals

def seed_youth(team, nation_config, league_lvl, season_label):
    """New world: the academy starts with players of every age from 15 to 19."""
    ref_year = int(season_label.split("/")[0])
    centre = youth_pa_centre(team, league_lvl)
    for age in range(15, MAX_YOUTH_AGE):
        for _ in range(intake_size(team)):
            team.youth.append(_new_youth(team, nation_config, centre, ref_year, age=age))
            
# PROMOTION AND DEMOTION

def promote(team, player):
    team.youth.remove(player)
    team.squad.append(player)
    
def demote(team, player):
    team.squad.remove(player)
    team.youth.append(player)
    
def ai_promotions(team, on_date):
    """Promote the best prospects where the club is short, or where they are better than the first-team players."""
    prospects = sorted(
        (p for p in team.youth if p.age_on(on_date) >= MIN_PROMOTION_AGE),
        key=lambda p: p.current_ability + 0.5 * p.potential_ability, reverse=True)
    promoted = []
    for p in prospects:
        in_position = [q.current_ability for q in team.squad if q.position == p.position]
        short = len(in_position) < TARGET_SQUAD[p.position]
        ready = (bool(in_position) and p.current_ability > min(in_position)
                 and len(team.squad) < MAX_SQUAD)
        if short or ready:
            promote(team, p)
            promoted.append(p)
    return promoted
    
def release_overage(team, on_date):
    released = [p for p in team.youth if p.age_on(on_date) >= MAX_YOUTH_AGE]
    keep = sorted((p for p in team.youth if p not in released),
                  key=lambda p: p.potential_ability, reverse=True)
    released += keep[MAX_YOUTH:]
    team.youth = keep[:MAX_YOUTH]
    team.released.extend(released)
    return released