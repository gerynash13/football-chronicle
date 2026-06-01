import random
from datetime import date, timedelta
from events import Event, Effect, Choice
from rules import get_match_days

NEWSPAPER_TEMPLATES = {
    "positive": [
        ("{team} showing impressive form — could this be their season?",     0.8),
        ("A local hero emerges at {team}",                                   0.5),
        ("{team} praised for commitment to developing local talent",          0.6),
        ("{team} draw praise from rival managers this week",                  0.7),
        ("Optimism surrounds {team} ahead of a busy schedule",               0.4),
    ],
    "negative": [
        ("Disappointing results for {team} — fans growing restless",         -0.6),
        ("Questions raised about {team}'s approach after poor run",          -0.3),
        ("{team} face growing calls for improved performances",              -0.4),
        ("Crisis talks reported at {team} as results fail to improve",       -0.7),
    ],
    "crowd": [
        ("Thin crowds at {team}'s recent fixtures cause concern",            -0.2),
        ("Supporter trust in {team} tested after tough run of results",      -0.3),
    ],
    "resilience": [
        ("Community rallies behind {team} after a difficult run",             0.3),
        ("{team} supporters refuse to give up despite poor form",             0.2),
    ],
    "neutral": [
        ("All eyes on {team} as the season reaches a crucial stage",          0.0),
        ("{team} face a pivotal week in their season",                        0.1),
        ("Analysts weigh in on {team}'s prospects for the months ahead",      0.0),
    ],
}

class GameCalendar:
    def __init__(self, season_year):
        self.season_year = season_year
        self.season_start, self.season_end = self._compute_season_dates()
        self.current_date = self.season_start
        self.scheduled_events = []  # List of Event objects
        self.inbox = []  # List of Event objects that have occurred but not yet read by the player
        
    def _compute_season_dates(self):
        start_year = int(self.season_year.split("/")[0])
        # First Sunday of September is the season start
        start = date(start_year, 9, 1)
        while start.weekday() != 6:
            start += timedelta(days=1)
        # Last Saturday of May is the season end
        end = date(start_year + 1, 5, 31)
        while end.weekday() != 6:
            end -= timedelta(days=1)
        return start, end
    
    def schedule_fixtures(self, competition, preferred_day: int | None = None, start_from_end: bool = False):
        # Assign real calendar dates to the fixtures based on the rules for match days
        # Pass the secondary day for the cup fixtures
        # Deterministic - safe to call multiple times without changing the schedule
        available_days = get_match_days(self.season_year)
        primary_day = preferred_day if preferred_day is not None else available_days[0]
        
        matchdays   = sorted(set(f["matchday"] for f in competition.fixtures))
        matchday_dates = {}
        if not start_from_end:
            current = self.season_start
            for matchday_num in matchdays:
                while current.weekday() != primary_day:
                    current += timedelta(days=1)
                # Skip dates taken by another competition
                occupied = {e.date for e in self.scheduled_events if e.category == "match"}
                while current in occupied:
                    current += timedelta(weeks=1)
                matchday_dates[matchday_num] = current
                current += timedelta(weeks=1)
        else:
            # Schedule matchdays backwards from season end so later rounds
            # (e.g. cup final) occur at the very end of the season.
            current = self.season_end
            for matchday_num in sorted(matchdays, reverse=True):
                while current.weekday() != primary_day:
                    current -= timedelta(days=1)
                occupied = {e.date for e in self.scheduled_events if e.category == "match"}
                while current in occupied:
                    current -= timedelta(weeks=1)
                matchday_dates[matchday_num] = current
                current -= timedelta(weeks=1)
            
        for fixture in competition.fixtures:
            fixture["date"] = matchday_dates[fixture["matchday"]]
            
        # Register one blocking match per event day
        for matchday_num, match_date in matchday_dates.items():
            self._add_event(Event(
                date=match_date,
                category="match",
                blocking=True,
                title=f"Matchday {matchday_num}",
                description=f"{len(competition.teams) // 2} matches scheduled for {match_date.strftime('%A, %d %B %Y')}.",
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
    
    def roll_dynamic_events(self, teams):
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
                    
    def _assess_team_context(self, team, competition):
        # Assess the team's current context (form, league position, fan sentiment) to determine event probabilities.
        # Placeholder for more complex logic that could consider recent results, league standing, etc.
        team_results = [
            r for r in competition.results
            if r["home_team"] == team.name or r["away_team"] == team.name
        ]
        recent = team_results[-5:]  # Last 5 matches
        
        wins = losses = 0
        for r in recent:
            if r["home_team"] == team.name:
                if r["home_goals"] > r["away_goals"]:
                    wins += 1
                elif r["home_goals"] < r["away_goals"]:
                    losses += 1
            else:
                if r["away_goals"] > r["home_goals"]:
                    wins += 1
                elif r["away_goals"] < r["home_goals"]:
                    losses += 1
                    
        return {
            "recent_wins":      wins,
            "recent_losses":    losses,
            "morale":           team.morale,
            "fan_satisfaction": team.fan_satisfaction,
            "has_results":      len(recent) > 0
        }
                    
    def generate_newspaper_story(self, teams, competition, probability=0.5):
        """
        Called after each matchday. Rolls for a context-aware newspaper event
        and schedules it for the next day if successful. The story's effects 
        are based on the team's current situation.
        """
        if random.random() > probability:
            return  # No event this time
        
        team = random.choice(teams)
        context = self._assess_team_context(team, competition)
        
        # Pick a template category based on context
        if not context["has_results"]:
            pool = NEWSPAPER_TEMPLATES["neutral"]  # No results yet, so stick to neutral stories
        elif context["recent_wins"] >= 3:
            pool = NEWSPAPER_TEMPLATES["positive"]  # Good run - positive story
        elif context["recent_losses"] >= 3:
            # Bad run - negative story, or community support story if morale hasn't dropped too much
            pool = (NEWSPAPER_TEMPLATES["negative"] + NEWSPAPER_TEMPLATES["resilience"]
                    if context["morale"] > -2
                    else NEWSPAPER_TEMPLATES["negative"])
        elif context["fan_satisfaction"] < 35:
            pool = NEWSPAPER_TEMPLATES["crowd"]  # Fan dissatisfaction stories
        elif context["recent_wins"] >= 2:
            pool = NEWSPAPER_TEMPLATES["positive"]  # Decent run - positive story
        elif context["recent_losses"] >= 2:
            pool = NEWSPAPER_TEMPLATES["negative"]  # Decent run - negative story
        else:
            pool = NEWSPAPER_TEMPLATES["neutral"]  # Decent run - neutral story
        
        # Pick a template and apply it to the team
        template, morale_delta = random.choice(pool)
        headline = template.format(team=team.name)
        
        # Schedule the vent for the next day, avoiding match days
        match_dates = set(e.date for e in self.scheduled_events if e.category == "match")
        publication_date = self.current_date + timedelta(days=1)
        while publication_date in match_dates:
            publication_date += timedelta(days=1)
            
        if publication_date > self.season_end:
            return  # Don't schedule events after the season ends
        
        effects = []
        if morale_delta != 0:
            effects.append(Effect(
                target_type="team",
                target_id=team.name,
                attribute="morale",
                value=morale_delta
            ))
            
        self.add_event(Event(
            date=publication_date,
            category="world",
            blocking=False,
            title="Local Newspaper",
            description=headline,
            effects=effects
        ))
        
    def schedule_player_meeting(self, player, team, from_date):
        """Schedule a blocking player interaction event, avoiding match days and duplicates."""
        # Don't schedule if a meeting for this player is already pending
        already_pending = any(
            e.category == "player_interaction"
            and e.related_player_id == player.id
            and e.date >= from_date
            for e in self.scheduled_events
        )
        if already_pending:
            return

        match_dates = set(e.date for e in self.scheduled_events if e.category == "match")

        meeting_date = from_date + timedelta(days=random.randint(2, 4))
        while meeting_date in match_dates or meeting_date > self.season_end:
            meeting_date += timedelta(days=1)

        if meeting_date > self.season_end:
            return

        self._add_event(Event(
            date=meeting_date,
            category="player_interaction",
            blocking=True,
            related_player_id=player.id,
            title=f"{player.name} Requests a Meeting",
            description=(
                f"{player.name} ({player.position}, {team.name}) has requested a meeting. "
                f"The player seems unsettled — morale is at {player.morale:.1f}."
            ),
            choices=[
                Choice(
                    text="Support them — listen and offer reassurance",
                    effects=[
                        Effect("player", player.id, "morale", +2.0),
                        Effect("player", player.id, "manager_relationship", +1.0)
                    ]
                ),
                Choice(
                    text="Dismiss their concerns — remind them of their duties",
                    effects=[
                        Effect("player", player.id, "morale", -0.5),
                        Effect("player", player.id, "manager_relationship", -1.5)
                    ]
                )
            ]
        ))
        
    def schedule_replay(self, competition, home_team, away_team, from_date):
        """
        Schedule a cup replay on the next available date after from_date.
 
        Adds the fixture to competition.fixtures with a new matchday number
        and registers a blocking match event on the calendar so the game loop
        stops and simulates it at the right time.
 
        Returns the scheduled date, or None if no date is available before
        the season ends.
 
        Why a new matchday number instead of reusing the drawn round's number?
        Because matchday numbers are how simulate_cup_round() finds its
        fixtures. If the replay shared a number with an already-completed
        round, it would be skipped by the completed_matchdays check.
        """
        existing_matchdays = [f["matchday"] for f in competition.fixtures] if competition.fixtures else []
        new_matchday = max(existing_matchdays) + 1 if existing_matchdays else 1
        
        # Find a date for the replay, skipping any day that already has a match
        candidate = from_date + timedelta(days=1)
        match_dates = set(e.date for e in self.scheduled_events if e.category == "match")
        while candidate <= self.season_end:
            if candidate not in match_dates:
                break
            candidate += timedelta(days=1)
            
        if candidate > self.season_end:
            return None  # No date available before the season ends
        
        competition.fixtures.append({
            "matchday": new_matchday,
            "home_team": home_team,
            "away_team": away_team,
            "date": candidate,
            "is_replay": True
        })
        
        self.add_event(Event(
            date=candidate,
            category="match",
            blocking=True,
            title=f"Replay: {home_team.name} vs {away_team.name}",
            description=f"Replay scheduled for {candidate.strftime('%A, %d %B %Y')}."
        ))
        
        return candidate
        
    def schedule_injury_notification(self, player, team, from_date):
        # Add injury news to inbox and schedule return reminder
        severity_labels = {
            "minor":        "a minor injury",
            "moderate":     "a moderate injury",
            "severe":       "a severe injury",
            "critical":     "a critical injury"
        }
        label = severity_labels.get(player.injury_severity, "an injury")
        
        def schedule_replay(self, competition, home_team, away_team, from_date):
            """Schedule a replay for a cup match on the next available midweek date.

            Adds a fixture to `competition.fixtures` with a new matchday number and
            schedules the match event on the calendar.
            """
            # Determine next matchday number
            existing_matchdays = [f["matchday"] for f in competition.fixtures] if competition.fixtures else []
            new_matchday = max(existing_matchdays) + 1 if existing_matchdays else 1

            # Find a date for the replay: prefer a midweek day (Wednesday)
            candidate = from_date + timedelta(days=1)
            match_dates = set(e.date for e in self.scheduled_events if e.category == "match")
            # Limit search to season end
            while candidate <= self.season_end:
                # Avoid existing match dates
                if candidate not in match_dates and candidate > from_date:
                    break
                candidate += timedelta(days=1)

            if candidate > self.season_end:
                return None

            # Add fixture and schedule event
            competition.fixtures.append({
                "matchday": new_matchday,
                "home_team": home_team,
                "away_team": away_team,
                "date": candidate
            })

            self._add_event(Event(
                date=candidate,
                category="match",
                blocking=True,
                title=f"Replay: {home_team.name} vs {away_team.name}",
                description=f"Replay scheduled for {candidate.strftime('%A, %d %B %Y')}"
            ))

            return candidate
        # Immediate inbox notification (background)
        self._add_event(Event(
            date=from_date,
            category="injury",
            blocking=False,
            title=f"{player.name} - Injury Update",
            description=(
                f"{player.name} ({team.name}) has suffered {label}."
                f"Expected to miss approximately {player.injury_matches_left} matches."
            )
        ))
        
        # Return reminder one matchday before the player is back
        if player.injury_matches_left > 1:
            match_dates = sorted(
                e.date for e in self.scheduled_events if e.category == "match"
            )
            future_matches = [d for d in match_dates if d > from_date]
            if len(future_matches) >= player.injury_matches_left - 1:
                reminder_date = future_matches[player.injury_matches_left - 2]
                self._add_event(Event(
                    date=reminder_date,
                    category="injury",
                    blocking=False,
                    title=f"{player.name} Returning Soon",
                    description=(
                        f"{player.name} is back in training and should be available "
                        f"for the next match."
                    )
                ))
                    
# Standalone helpers
def apply_effects(effects, teams):
    # Apply a list of effects to the game world. 
    # Effects can target teams or players and modify their attributes.
    team_map_id = {t.id: t for t in teams}
    team_map_name = {t.name: t for t in teams}
    player_map_id = {p.id: p for t in teams for p in t.squad}
    # Legacy saves / events may still reference players by name
    player_map_name = {p.name: p for t in teams for p in t.squad}
    
    BOUNDS = {
        "morale": (-10, 10),
        "board_confidence": (0, 100),
        "fan_satisfaction": (0, 100),
        "manager_relationship": (-5, 5)
    }
    
    for effect in effects:
        if effect.target_type == "team":
            target = team_map_id.get(effect.target_id) or team_map_name.get(effect.target_id)
        else:
            target = player_map_id.get(effect.target_id) or player_map_name.get(effect.target_id)
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