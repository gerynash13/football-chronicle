"""Run the world headlessly and print health numbers.  Usage: python calibrate.py [seasons] [seed] [start_year]"""
import sys, tempfile, statistics
from collections import Counter
from classes import GameEngine
from save_slot import SaveSlot

NAN = float("nan")


def pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx and sy else NAN


def top11_level(team):
    cas = sorted((p.current_ability for p in team.squad if not p.is_retired), reverse=True)[:11]
    return statistics.mean(cas) if cas else 0


def available(team):
    return sum(not (p.is_retired or p.is_injured or p.is_suspended) for p in team.squad)


def run(seasons=30, seed=1, start_year=1896):
    with tempfile.TemporaryDirectory() as tmp:
        engine = GameEngine(start_year, seasons, seed=seed, slot=SaveSlot("calib", root=tmp))
        state = engine.advance()
        matches = goals = home = draw = away = forfeits = 0
        strength, min_avail = {}, 99
        print(f"{'season':8}{'goals/g':>8}{'home%':>7}{'draw%':>7}{'away%':>7}{'r(str,pts)':>11}"
              f"{'avgCA':>7}{'avgAge':>8}{'alumni':>8}{'minSquad':>10}{'minAvail':>9}{'forfeits':>9}"
              f"{'youth':>7}{'released':>9}{'myria':>8}{'tier':>11}")
        while state["type"] not in ("game_over", "error"):
            if state["type"] == "blocking_event":
                state = engine.choose(0)
                continue
            if state["type"] == "matchday":
                min_avail = min(min_avail, min(available(t) for t in engine.teams))
                for r in state["results"]:
                    forfeits += sum(1 for e in r["events"] if e["type"] == "forfeit")
                    if engine.comp is None or r["competition"] != engine.comp.name:
                        continue                       # statistics follow the focus league
                    if not strength:
                        strength = {t.name: top11_level(t) for t in engine.teams}
                    matches += 1
                    goals += r["home_goals"] + r["away_goals"]
                    home += r["home_goals"] > r["away_goals"]
                    draw += r["home_goals"] == r["away_goals"]
                    away += r["home_goals"] < r["away_goals"]
            elif state["type"] == "season_end":
                pts = {r["team"]: r["points"] for r in state["final_standings"]}
                corr = pearson([strength[n] for n in pts], [pts[n] for n in pts]) \
                    if pts and strength else NAN
                n = matches or NAN
                league = engine._league_teams() or engine.teams
                players = [p for t in league for p in t.squad]
                end = engine.calendar.season_end
                nation = engine._nations["myria"]
                print(f"{state['season']:8}{goals / n:8.2f}{100 * home / n:7.1f}{100 * draw / n:7.1f}"
                      f"{100 * away / n:7.1f}{corr:11.2f}"
                      f"{statistics.mean(p.current_ability for p in players):7.1f}"
                      f"{statistics.mean(p.age_on(end) for p in players):8.1f}"
                      f"{sum(len(t.retired) for t in engine.teams):8d}"
                      f"{min(sum(not p.is_retired for p in t.squad) for t in engine.teams):10d}"
                      f"{min_avail:9d}{forfeits:9d}"
                      f"{statistics.mean(len(t.youth) for t in engine.teams):7.1f}"
                      f"{sum(len(t.released) for t in engine.teams):9d}"
                      f"{nation.prestige:8.0f}{nation.tier:>11}")
                matches = goals = home = draw = away = forfeits = 0
                strength, min_avail = {}, 99
            state = engine.advance()
        if engine.comp:
            titles = Counter(c["winner"] for c in engine.archive.champions(engine.comp.key))
            print("Titles:", titles.most_common())


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 30,
        int(sys.argv[2]) if len(sys.argv) > 2 else 1,
        int(sys.argv[3]) if len(sys.argv) > 3 else 1896)