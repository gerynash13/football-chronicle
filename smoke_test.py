from classes import GameEngine

engine = GameEngine(start_year=1896, num_seasons=1)
state = engine.advance()
if state["type"] == "blocking_event":
    engine.choose(0)
while state["type"] not in ("season_end", "game_over"):
    state = engine.advance()
    if state["type"] == "blocking_event":
        state = engine.choose(0)

print("=== Daily Sulhavon, own team's results ===")
for art in engine.newsroom.get_articles(team="Kluba Sulhavonos", journalist_id="the_daily_sulhavon"):
    print(f"\n{art.headline}")
    print(f"  {art.body}")
    print(f"  players: {art.players}")