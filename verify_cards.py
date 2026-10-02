import os
for f in ["teams_data.json", "competition_data.json", "records_data.json"]:
    if os.path.exists(f):
        os.remove(f)

from classes import GameEngine

engine = GameEngine(start_year=2000, num_seasons=1)
state = engine.advance()

matches_simulated = 0
suspensions_seen = 0

while state["type"] not in ("game_over", "error"):
    if state["type"] == "blocking_event":
        state = engine.choose(0)
        continue
    if state["type"] == "matchday":
        matches_simulated += len(state["results"])
        suspensions_seen += len(state.get("newly_suspended", []))
        recorded_matches = sum(len(comp.results) for comp in engine.competitions)
        assert recorded_matches == matches_simulated, (
            f"results length drifted: {recorded_matches} vs {matches_simulated}"
        )
    state = engine.advance()
    
total_career_yellows = sum(p.career_yellow_cards for t in engine.teams for p in t.squad)
total_career_reds    = sum(p.career_red_cards    for t in engine.teams for p in t.squad)
print(f"Career yellow cards recorded: {total_career_yellows}")
print(f"Career red cards recorded: {total_career_reds}")

print(f"Matches simulated: {matches_simulated}")
print(f"Suspensions triggered: {suspensions_seen}")
print("Invariant held — no duplicate results.")