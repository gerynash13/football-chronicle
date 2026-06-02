#!/usr/bin/env python3
"""
Debug script to drive the game forward and inspect cup bracket when replays occur.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:5000/api"

def advance(load_save=False):
    """Call /api/advance and return the state."""
    resp = requests.post(f"{BASE_URL}/advance", json={"load_save": load_save})
    return resp.json()

def choose(index=0):
    """Respond to a blocking event with a choice."""
    resp = requests.post(f"{BASE_URL}/choose", json={"index": index})
    return resp.json()

def get_bracket():
    """Get the current cup bracket."""
    resp = requests.get(f"{BASE_URL}/cup_bracket")
    return resp.json()

def main():
    print("Starting game with load_save=True...")
    state = advance(load_save=True)
    print(f"Initial state: {state['type']}\n")
    
    turns = 0
    max_turns = 500
    
    while turns < max_turns:
        state = advance()
        turns += 1
        
        stype = state.get("type")
        season = state.get("season", "?")
        comp = state.get("competition", "?")
        
        # Handle blocking events by choosing option 0
        if stype == "blocking_event":
            print(f"[Turn {turns}] Blocking event: {state.get('title')} -> choosing option 0")
            state = choose(0)
            stype = state.get("type")
        
        # Print matchday info
        if stype == "matchday":
            print(f"[Turn {turns}] {stype} - Season {season}, {comp}")
            
            # Get bracket and check for replays
            bracket = get_bracket()
            if bracket.get("rounds") and comp == "Protonas Cup":
                # Always show cup bracket during cup rounds
                print("\n=== CURRENT BRACKET ===")
                print(json.dumps(bracket, indent=2))
                print("=== END BRACKET ===\n")
                
                has_replays = False
                replay_count = 0
                
                for round_info in bracket["rounds"]:
                    for fixture in round_info["fixtures"]:
                        if fixture.get("is_replay"):
                            has_replays = True
                            replay_count += 1
                        if fixture.get("is_draw"):
                            print(f"  Draw: {fixture['home']} vs {fixture['away']} -> {fixture.get('score_display')}")
                
                if has_replays:
                    print(f"  >> FOUND {replay_count} REPLAY(S) IN BRACKET!")
                    
                    # Check for TBD issues
                    for round_info in bracket["rounds"]:
                        for fixture in round_info["fixtures"]:
                            if fixture.get("home") == "TBD" or fixture.get("away") == "TBD":
                                print(f"  !! TBD FOUND: {fixture}")
                    
                    if replay_count >= 2:
                        print(f"Found {replay_count} replays. Exiting.")
                        return
        
        elif stype == "season_end":
            print(f"[Turn {turns}] Season {season} ended. Champion: {state.get('champion')}")
        
        else:
            print(f"[Turn {turns}] {stype}")
    
    print(f"Reached max turns ({max_turns}) without finding multiple replays.")

if __name__ == "__main__":
    main()
