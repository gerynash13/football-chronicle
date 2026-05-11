from datetime import date, timedelta
from events import Event, Effect
from rules import get_match_days

class GameCalendar:
    def __init__(self, season_year):
        self.season_year = season_year
        self.season_start, self.season_end = self._compute_season_dates()
        self.current_date = self.season_start
        self.scheduled_events = []  # List of Event objects
        self.inbox = []  # List of Event objects that have occurred but not yet read by the player
        
    def _compute_season_dates(self):
        start_year = int(self.season_year.split("/")[0])
        # First Saturday of September is the season start
        start = date(start_year, 9, 1)
        while start.weekday() != 5:
            start += timedelta(days=1)
        # Last Saturday of May is the season end
        end = date(start_year + 1, 5, 31)
        while end.weekday() != 5:
            end -= timedelta(days=1)
        return start, end
    
    def schedule_fixtures(self, competition):
        # Assign real calendar dates to the fixtures based on the rules for match days
        # Deterministic - safe to call multiple times without changing the schedule
        primary_day = get_match_days(self.season_year)[0]
        matchdays   = sorted(set(f["matchday"] for f in competition.fixtures))
        current     = self.season_start
        
        matchday_dates = {}
        for matchday_num in matchdays:
            while current.weekday() != primary_day:
                current += timedelta(days=1)
            matchday_dates[matchday_num] = current
            current += timedelta(weeks=1)  # Move to the next week for the next matchday
            
        for fixture in competition.fixtures:
            fixture["date"] = matchday_dates[fixture["matchday"]]
            
        # Register one blocking match per event day
        for matchday_num, match_date in matchday_dates.items():
            self._add_event(Event(
                date=match_date,
                category="match",
                blocking=True,
                title=f"Matchday {matchday_num}",
                description=f"{len((competition.teams) // 2)} matches scheduled for {match_date.strftime('%A, %d %B %Y')}. Prepare your team!"
            ))
            
    def _add_event(self, event):
        self.scheduled_events.append(event)
        self.scheduled_events.sort(key=lambda e: e.date)  # Ensure events are in chronological order
        
    def add_event(self, event):
        # Add event to inbox and schedule it
        self._add_event(event)
        
    def get_events_for_date(self, target_date):
        # Return events scheduled for the target date
        return [e for e in self.scheduled_events if e.date == target_date]
    
    def get_next_event_date(self, from_date=None):
        # Return the date of the next scheduled event after from_date (or current date if None)
        if from_date is None:
            from_date = self.current_date
        future_events = [e for e in self.scheduled_events if e.date >= from_date]
        return future_events[0].date if future_events else None
    
    def roll_dynamic_events(self):
        """
        Probabilistically generate dynamic events for today.
        Stub - each new events slots here as we build it.
        """
        return []  # Placeholder for dynamic event generation logic
    
    def apply_weekly_decay(self, teams):
        # Decay all morale and relationship values by 10% toward neutral. Called on the first day of each week.
        for team in teams:
            team.morale = round(team.morale * 0.9, 2)
            if abs(team.morale) < 0.1:
                team.morale = 0.0
            for player in team.squad:
                player.morale = round(player.morale * 0.9, 2)
                player.manager_relationship = round(player.manager_relationship * 0.95, 2)
                if abs(player.morale) < 0.1:
                    player.morale = 0.0
                if abs(player.manager_relationship) < 0.1:
                    player.manager_relationship = 0.0
                    
# Standalone helpers
def apply_effects(effects, teams):
    # Apply a list of effects to the game world. 
    # Effects can target teams or players and modify their attributes.
    team_map    = {t.name: t for t in teams}
    player_map  = {p.name: p for t in teams for p in t.squad}
    
    BOUNDS = {
        "morale": (-10, 10),
        "board_confidence": (0, 100),
        "fan_satisfaction": (0, 100),
        "manager_relationship": (-5, 5)
    }
    
    for effect in effects:
        target = (team_map if effect.target_type == "team" else player_map).get(effect.target_id)
        if not target:
            continue  # Invalid target, skip this effect
        lo, hi = BOUNDS.get(effect.attribute, (-10, 10))
        current = getattr(target, effect.attribute, 0.0)
        setattr(target, effect.attribute, round(max(lo, min(hi, current + effect.value)), 2))
        
def apply_match_morale(home_team, away_team, home_goals, away_goals):
    # Adjust team morale based on match result. 
    if home_goals > away_goals:
        deltas = (1.5, -1.5) # Home win
    elif home_goals < away_goals:
        deltas = (-1.5, 1.5) # Away win
    else:
        deltas = (0.3, 0.3)  # Draw
        
    home_team.morale = round(max(-10, min(10, home_team.morale + deltas[0])), 2)
    away_team.morale = round(max(-10, min(10, away_team.morale + deltas[1])), 2)