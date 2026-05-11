def get_max_subs(season_year):
    start_year = int(season_year.split("/")[0])
    if start_year < 1965:
        return 0
    elif start_year < 2020:
        return 3
    else:
        return 5
    
def get_match_days(season_year):
    """
    Weekdays on which matches can be scheduled (0=Monday, 6=Sunday)
    Returns a list of integers representing the allowed match days. First entry is the default match day.
    """
    start_year = int(season_year.split("/")[0])
    if start_year < 1960:
        return [6, 5]  # Sunday and Saturday
    elif start_year < 1990:
        return [6, 5, 2]  # Sunday, Saturday, and Wednesday
    else:
        return [6, 5, 2, 1]  # Sunday, Saturday, Wednesday, and Tuesday