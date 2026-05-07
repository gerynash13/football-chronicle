"""
Nation configuration for player configuration.
Each nation has:
    - tier: description of the nation's footballing strength (e.g. "top-tier", "mid-tier", "lower-tier")
    - pa_cap: the maximum potential ability for players from that nation
    - wonderkid_pa_cap: the maximum potential ability for wonderkids from that nation
    - wonderkid_chance: probability (0-1) that a player from that nation will be a wonderkid
"""
    
NATIONS = {
    "Myria": {
        "tier": "low-tier",
        "pa_cap": 85,
        "wonderkid_pa_cap": 100,
        "wonderkid_chance": 0.04
    },
}

TIER_DEFAULTS = {
    "top-tier":     {"pa_cap": 180, "wonderkid_pa_cap": 200, "wonderkid_chance": 0.08},
    "high-tier":    {"pa_cap": 150, "wonderkid_pa_cap": 170, "wonderkid_chance": 0.06},
    "mid-tier":     {"pa_cap": 120, "wonderkid_pa_cap": 140, "wonderkid_chance": 0.05},
    "low-tier":     {"pa_cap": 85,  "wonderkid_pa_cap": 100, "wonderkid_chance": 0.04},
    "lower-tier":   {"pa_cap": 70,  "wonderkid_pa_cap": 82,  "wonderkid_chance": 0.02},
}

def get_nation_config(nation_name):
    if nation_name not in NATIONS:
        raise ValueError(f"Nation '{nation_name}' not found in configuration.")
    return NATIONS[nation_name]