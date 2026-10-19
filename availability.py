def tick_suspensions(players) -> None:
    """One match has passed; tick down suspension counters."""
    for p in players:
        if p.suspension_matches_left > 0:
            p.suspension_matches_left -= 1
            if p.suspension_matches_left == 0:
                p.is_suspended = False
                
def heal_injuries(teams, today):
    """Injuries heal with time, not with matches."""
    for team in teams:
        for p in team.squad:
            if p.is_injured and (p.injury_until is None or today > p.injury_until):
                p.is_injured = False
                p.injury_severity = None
                p.injury_matches_left = 0
                p.injury_until = None