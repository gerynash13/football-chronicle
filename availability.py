def tick_availability(players) -> None:
    """One match has passed for these players: shorten bans and injuries."""
    for p in players:
        if p.suspension_matches_left >= 0:
            p.suspension_matches_left -= 1
            if p.suspension_matches_left == 0:
                p.is_suspended = False
        if p.injury_matches_left >= 0:
            p.injury_matches_left -= 1
            if p.injury_matches_left == 0:
                p.is_injured = False
                p.injury_severity = None