import math

HOME_BONUS              = 6.0
CHANCES_PER_MATCH       = 36
POSSESSION_SCALE        = 40.0
CONVERSION_SCALE        = 65.0
BASE_CONVERSION         = 0.09
MIN_CONVERSION, MAX_CONVERSION = 0.1, 0.40
SHOT_ON_TARGET          = 0.30
MORALE_POINTS           = 0.3
MIN_PLAYERS             = 7
INJURY_PER_TACKLE       = 0.015
OFF_MATCH_INJURY_RATE   = 0.004
INJURY_DAYS_PER_MATCH   = 7
def possession_share(mid_a, mid_b):
    return 1 / (1 + math.exp(-(mid_a - mid_b) / POSSESSION_SCALE))

def goal_probability(edge):
    p = BASE_CONVERSION * math.exp(edge / CONVERSION_SCALE)
    return max(MIN_CONVERSION, min(MAX_CONVERSION, p))