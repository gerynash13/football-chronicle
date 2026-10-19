"""Club facilities, each 0-100. Later: upgraded with money, decay without maintenance."""
DEFAULT_FACILITIES = {
    "stadium": 50,
    "training": 50,
    "youth": 50,
    "youth_recruitment": 50,
}

def facilities_from_config(overrides):
    return {**DEFAULT_FACILITIES, **(overrides or {})}