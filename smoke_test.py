from classes import GameEngine
from data_loader import journalists_for_season
from newsroom import covers_event

engine = GameEngine(start_year=1896, num_seasons=1)
state = engine.advance()
if state["type"] == "blocking_event":
    state = engine.choose(0)

while state["type"] not in ("season_end", "game_over"):
    state = engine.advance()
    if state["type"] == "blocking_event":
        state = engine.choose(0)

events = engine.news_feed.get_recent(5)
roster = journalists_for_season(engine.season_year)

print("=== Real events this season ===")
for evt in events:
    print(f"\n[{evt['type']}] {evt.get('home_team')} vs {evt.get('away_team')}")
    for j in roster:
        verdict = "covers" if covers_event(j, evt, engine.teams) else "skips"
        print(f"  {j.name:28s} ({j.tier:10s}) -> {verdict}")

synthetic_global_event = {"type": "record_broken", "home_team": "Kluba Sulhavonos"}
print("\n=== Synthetic global-magnitude event (hand-built — nothing live produces this yet) ===")
for j in roster:
    verdict = "covers" if covers_event(j, synthetic_global_event, engine.teams) else "skips"
    print(f"  {j.name:28s} ({j.tier:10s}) -> {verdict}")