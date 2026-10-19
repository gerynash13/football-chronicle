"""Retirement and youth intake: what keeps the world alive between seasons."""
import statistics

from name_generator import generate_youth

TARGET_SQUAD = {"GK": 2, "DEF": 4, "MID": 4, "FWD": 6}
CLUB_WEIGHT = 0.3   # how much the first team level affects youth intake
YOUTH_FACILITY_POINTS = 8  # youth facility 100 = +8 ability level, 0 = -8

def _top_level(players):
    cas = sorted((p.current_ability for p in players if not p.is_retired), reverse=True)[:11]
    return sum(cas) / len(cas) if cas else 40.0

def top11_level(team):
    squad = getattr(team, "squad", team)
    cas = sorted((p.current_ability for p in squad if not p.is_retired), reverse=True)[:11]
    return statistics.mean(cas) if cas else 0

def league_level(teams):
    return sum(_top_level(t.squad) for t in teams) / len(teams)

def retire_players(team, season_label):
    gone = [p for p in team.squad if p.is_retired]
    for p in gone:
        p.retired_season = season_label
    team.squad = [p for p in team.squad if not p.is_retired]
    team.retired.extend(gone)
    return gone

def youth_intake(team, nation_config, league_lvl, next_season_label):
    ref_year = int(next_season_label.split("/")[0])
    base = CLUB_WEIGHT * top11_level(team.squad) + (1 - CLUB_WEIGHT) * league_lvl
    level = base + YOUTH_FACILITY_POINTS * (team.facilities["youth"] - 50) / 50
    wonder_mult = 0.5 + team.facilities["youth_recruitment"] / 100
    arrivals = []
    for position, target in TARGET_SQUAD.items():
        have = sum(1 for p in team.squad if p.position == position)
        for _ in range(max(0, target - have)):
            youth = generate_youth(position, level, team.nation_id, nation_config,
                                   ref_year, team.home_region)
            team.squad.append(youth)
            arrivals.append(youth)
    return arrivals 