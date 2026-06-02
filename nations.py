from data_loader import get_nation, load_nations, TIER_STATS, prestige_to_tier

# Keep TIER_DEFAULTS exported so any code that imports nations.py can use it
TIER_DEFAULTS = TIER_STATS

def get_nation_config(nation_name: str) -> dict:
    """
    Backward-compatible acccessor.
    Accepts either a nation id (e.g. "myria") or a nation name (e.g. "Myria").
    Returns the dict shape the old code expected.
    """
    # Try by id first (lowercase match)
    try:
        nation = get_nation(nation_name.lower())
        return nation.to_player_config()
    except ValueError:
        pass
    
    # Fall back to matching by display name
    all_nations = load_nations()
    for nation in all_nations.values():
        if nation.name.lower() == nation_name.lower():
            return nation.to_player_config()
        
    raise ValueError(
        f"Nation '{nation_name}' not found in nations.yaml."
    )