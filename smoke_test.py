import os
for f in ["teams_data.json", "competition_data.json", "records_data.json"]:
    if os.path.exists(f): 
        os.remove(f)
    
from classes import GameEngine

engine = GameEngine(start_year=1896, num_seasons=1)
state = engine.advance()

while state["type"] not in ("game_over", "error"):
    if state["type"] == "blocking_event":
        state = engine.choose(0)
        continue
    if state["type"] == "season_end":
        print(f"Champion: {state['champion']}")
        print(f"Top Scorer: {state['top_scorers'][0]['name']}"
              f" ({state['top_scorers'][0]['goals']}) goals")
        print(f"Top Assists: {state['top_assisters'][0]['name']}"
              f" ({state['top_assisters'][0]['assists']}) assists")
        if state["top_rated"]:
            print(f"Top Rated: {state['top_rated'][0]['name']}"
                  f" ({state['top_rated'][0]['avg_rating']})")
        print(f"News Feed: {len(engine.news_feed)} events")
    state = engine.advance()
    
print(f"Finished: {state['type']}")