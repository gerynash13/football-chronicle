from collections import defaultdict

FORMATION = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 5}  # 2-3-5 Pyramid
MISSING_SLOT_RATING = 20.0  # an empty seat counts as a very poor player
OUT_OF_POSITION_FACTOR = 0.6  # e.g. a midfielder in a goalkeeper's slot

ATTACK_FWD = {"finishing": .35, "positioning": .25, "dribbling": .20, "pace": .20}
ATTACK_MID = {"passing": .5, "vision": .5}
MID_ALL    = {"passing": .3, "vision": .3, "stamina": .2, "tackling": .2}
DEF_ALL    = {"tackling": .35, "positioning": .30, "heading": .20, "pace": .15}
GK_ALL     = {"reflexes": .40, "positioning": .30, "handling": .15, "command": .15}

LINES = {
    "attack":   [("FWD", 0.65, ATTACK_FWD), ("MID", 0.35, ATTACK_MID)],
    "midfield": [("MID", 1.0, MID_ALL)],
    "defense":  [("DEF", 0.70, DEF_ALL), ("GK", 0.30, GK_ALL)],
}

def _skill(player, weights, slot):
    if player.position != slot:
        return OUT_OF_POSITION_FACTOR * player.current_ability
    return sum(player.attributes[k] * w for k, w in weights.items())

def line_ratings(xi):
    by_slot = defaultdict(list)
    for p in xi:
        by_slot[p.playing_as or p.position].append(p)
    ratings = {}
    for line, parts in LINES.items():
        total = 0.0
        for slot, weight, weights in parts:
            players = by_slot[slot]
            have = sum(_skill(p, weights, slot) for p in players)
            missing = max(0, FORMATION[slot] - len(players))
            total += weight * (have + missing * MISSING_SLOT_RATING) / FORMATION[slot]
        ratings[line] = total
    return ratings