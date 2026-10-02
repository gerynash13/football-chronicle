import random
from classes import GameEngine

engine = GameEngine(start_year=1896, num_seasons=1)
state = engine.advance()
if state["type"] == "blocking_event":
    state = engine.choose(0)  # pick a club

all_players = [p for t in engine.teams for p in t.squad]
sample = random.sample(all_players, 5)

for p in sample:
    print(f"\n{p.name} — {p.position}, CA {p.current_ability}")
    for trait, value in sorted(p.personality.items(), key=lambda kv: -kv[1]):
        print(f"  {trait:22s} {value:3d}")