import os, datetime, statistics

for f in ["teams_data.json", "competition_data.json", "records_data.json", "world_state.json"]:
    if os.path.exists(f):
        os.remove(f)

from classes import GameEngine

engine = GameEngine(start_year=1896, num_seasons=6)
state = engine.advance()                        # loads the world, returns the club-selection event
players = [p for t in engine.teams for p in t.squad]
start = datetime.date(1896, 9, 1)
ca0   = {p.id: p.current_ability for p in players}
age0  = {p.id: p.age_on(start) for p in players}

while state["type"] not in ("game_over", "error"):
    state = engine.choose(0) if state["type"] == "blocking_event" else engine.advance()

avg = lambda xs: statistics.mean(xs) if xs else float("nan")
young = [p.current_ability - ca0[p.id] for p in players if age0[p.id] <= 22]
old   = [p.current_ability - ca0[p.id] for p in players if age0[p.id] >= 29]
print(f"Players: {len(players)}   ages at start: {min(age0.values())}-{max(age0.values())}")
print(f"Mean CA change over 6 seasons, age <=22: {avg(young):+.1f} (n={len(young)})")
print(f"Mean CA change over 6 seasons, age >=29: {avg(old):+.1f} (n={len(old)})")

end = engine.calendar.season_end
retired  = [p for p in players if p.is_retired]
eligible = [p for p in players if p.age_on(end) >= 35]
print(f"Retired: {len(retired)}   Eligible (35+): {len(eligible)}")
assert len(retired) <= len(eligible)

for key in ("all:player_youngest_scorer", "all:player_oldest_scorer"):
    r = engine.record_book.extremes.get(key)
    print(key, r.value if r else None)

import api
api.engine = engine        # routes look `engine` up at call time, so this redirects them
print("API age:", api.app.test_client().get(f"/api/player/{players[0].id}").get_json()["age"])