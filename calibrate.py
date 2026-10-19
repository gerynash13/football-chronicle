"""Run the world headlessly and print health numbers. Usage: python3 calibrate.py [seasons] [seed]"""
import sys, tempfile, statistics
from classes import GameEngine
from save_slot import SaveSlot
from lifecycle import top11_level

def pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    sx = sum((x - mx) ** 2 for x in xs) ** 0.5
    sy = sum((y - my) ** 2 for y in ys) ** 0.5
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy) if sx * sy else float("nan")

def run(seasons=30, seed=1, start_year=1896):
    with tempfile.TemporaryDirectory() as tmp:
        engine = GameEngine(start_year, seasons, seed=seed, slot=SaveSlot("calib", root=tmp))
        state = engine.advance()
        matches = goals = home = draw = away = 0
        min_avail, forfeits = 99, 0
        strength = {}
        print(f"{'season':8}{'goals/g':>8}{'home%':>7}{'draw%':>7}{'away%':>7}"
              f"{'r(str,pts)':>11}{'avgCA':>7}{'avgAge':>8}{'alumni':>9}{'minSquad':>10}"
              f"{'minAvail':>9}{'forfeits':>9}")
        while state["type"] not in ("game_over", "error"):
            if state["type"] == "blocking_event":
                state = engine.choose(0)
                continue
            if state["type"] == "matchday":
                min_avail = min(min_avail, min(available(t) for t in engine.teams))
                forfeits += sum(1 for r in state["results"]
                                for e in r["events"] if e["type"] == "forfeit")
            if state["type"] == "matchday" and state["competition_type"] == "league":
                if not strength:
                    strength = {t.name: top11_level(t) for t in engine.teams}
                for r in state["results"]:
                    matches += 1
                    goals += r["home_goals"] + r["away_goals"]
                    if r["home_goals"] > r["away_goals"]:
                        home += 1
                    elif r["home_goals"] < r["away_goals"]:
                        away += 1
                    else:
                        draw += 1
            elif state["type"] == "season_end":
                pts = {r["team"]: r["points"] for r in state["final_standings"]}
                corr = pearson([strength[n] for n in pts], [pts[n] for n in pts])
                players = [p for t in engine.teams for p in t.squad]
                end = engine.calendar.season_end
                print(f"{state['season']:8}{goals / matches:8.2f}{100 * home / matches:7.1f}"
                      f"{100 * draw / matches:7.1f}{100 * away / matches:7.1f}{corr:11.2f}"
                      f"{statistics.mean(p.current_ability for p in players):7.1f}"
                      f"{statistics.mean(p.age_on(end) for p in players):8.1f}"
                      f"{sum(len(t.retired) for t in engine.teams):9d}"
                      f"{min(sum(not p.is_retired for p in t.squad) for t in engine.teams):10d}"
                      f"{min_avail:9d}{forfeits:9d}")
                matches = goals = home = draw = away = 0
                min_avail, forfeits = 99, 0
                strength = {}
            state = engine.advance()
            
def available(team):
    return sum(not (p.is_retired or p.is_injured or p.is_suspended) for p in team.squad)
            
if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 30,
        int(sys.argv[2]) if len(sys.argv) > 2 else 1)