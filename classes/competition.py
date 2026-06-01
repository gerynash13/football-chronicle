import random
from simulation import simulate_match
from player_refs import xi_entry, new_competition_id

class Competition:
    def __init__(self, name, teams, competition_type="league", max_subs=0, season_year="1896/97"):
        self.id = new_competition_id()
        self.name = name
        self.teams = teams
        self.type = competition_type
        self.current_matchday = 1
        self.fixtures = []
        self.results = []
        self.standings = self.initialize_standings()
        self.completed_matchdays = set()
        self.max_subs = max_subs
        self.season_year = season_year
        
    def initialize_standings(self):
        standings = {}
        for team in self.teams:
            standings[team.name] = {
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "points": 0
            }
        return standings
    
    def generate_fixtures(self):
        n = len(self.teams)
        
        # For round-robin, we need an even amount of teams
        # If not even, add a bye (None)
        teams = self.teams.copy()
        if n % 2 == 1:
            teams.append(None)
            n += 1
            
        fixtures = []
        
        # Generate first half of the season
        for round_num in range(n - 1):
            for i in range(n // 2):
                home = teams[i]
                away = teams[n - 1 - i]
                
                if home is not None and away is not None:
                    fixtures.append({
                        "matchday": round_num + 1,
                        "home_team": home,
                        "away_team": away
                    })
                
            # Rotate teams (keep first team fixed)
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    
        # Store first half of fixtures
        self.fixtures = fixtures.copy()
        
        # Generate second half of fixtures
        last_matchday = n - 1
        for fixture in fixtures:
            self.fixtures.append({
                "matchday": fixture["matchday"] + last_matchday,
                "home_team": fixture["away_team"],
                "away_team": fixture["home_team"]
            })

    def get_current_fixtures(self):
        return [f for f in self.fixtures if f["matchday"] == self.current_matchday]
    
    
    def simulate_matchday(self):
        # Check if matchday has already been simulated
        if self.current_matchday in self.completed_matchdays:
            return
        
        # Simulate matches
        for fixture in self.fixtures:
            if fixture["matchday"] == self.current_matchday:
                home_team = fixture["home_team"]
                away_team = fixture["away_team"]
                
                home_goals, away_goals, events, ratings, home_xi, away_xi = simulate_match(
                    home_team, away_team, max_subs=self.max_subs, season_year=self.season_year
                )
                
                self.results.append({
                    "home_team": home_team.name,
                    "away_team": away_team.name,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "events": events,
                    "ratings": ratings,
                    "home_xi": [xi_entry(p) for p in home_xi],
                    "away_xi": [xi_entry(p) for p in away_xi],
                    "competition": self.name,
                    "season": self.season_year,
                })
                
                # Update standings
                self.standings[home_team.name]["played"] += 1
                self.standings[away_team.name]["played"] += 1

                self.standings[home_team.name]["goals_for"] += home_goals
                self.standings[home_team.name]["goals_against"] += away_goals
                self.standings[home_team.name]["goal_difference"] = \
                    self.standings[home_team.name]["goals_for"] - self.standings[home_team.name]["goals_against"]

                self.standings[away_team.name]["goals_for"] += away_goals
                self.standings[away_team.name]["goals_against"] += home_goals
                self.standings[away_team.name]["goal_difference"] = \
                    self.standings[away_team.name]["goals_for"] - self.standings[away_team.name]["goals_against"]

                # Determine result
                if home_goals > away_goals:
                    self.standings[home_team.name]["wins"] += 1
                    self.standings[home_team.name]["points"] += 2
                    self.standings[away_team.name]["losses"] += 1
                elif away_goals > home_goals:
                    self.standings[away_team.name]["wins"] += 1
                    self.standings[away_team.name]["points"] += 2
                    self.standings[home_team.name]["losses"] += 1
                else:
                    self.standings[home_team.name]["draws"] += 1
                    self.standings[home_team.name]["points"] += 1
                    self.standings[away_team.name]["draws"] += 1
                    self.standings[away_team.name]["points"] += 1
        
        # Mark matchday as completed            
        self.completed_matchdays.add(self.current_matchday)
                
    def advance_matchday(self):
        # Non-interactive environment: simply advance the matchday counter.
        # Removed blocking input() so the engine can run headless (API/web).
        self.current_matchday += 1
        
    
    def get_standings(self):
        return self.standings
    
    @property
    def total_rounds(self):
        """Total rounds/matchdays in the competition"""
        if not self.fixtures:
            return 0
        return max(f["matchday"] for f in self.fixtures)


class CupCompetition(Competition):
    """Simple knockout cup with auto-scaling to next power of two.

    Fixtures are generated per round with `matchday` representing the round number.
    """
    def __init__(self, name, teams, max_subs=0, season_year="1896/97"):
        super().__init__(name, teams, competition_type="cup", max_subs=max_subs, season_year=season_year)

    def _next_power_of_two(self, n):
        p = 1
        while p < n:
            p *= 2
        return p

    def simulate_cup_round(self):
        """
        Simulate the current cup round and build the next round's fixtures.
 
        Draws are NOT resolved here. Instead, each drawn fixture is included
        in the returned list so the caller (the game loop) can schedule a
        calendar replay for a future date.
 
        Returns a list of drawn fixture dicts — empty if no draws occurred.
        Each entry has the shape:
            {"home_team": <Team>, "away_team": <Team>}
 
        Next-round fixtures are only built from matches that produced a
        clear winner this round. Drawn bracket slots remain open until the
        replay is simulated and advance_cup_winner() is called.
 
        Why return draws instead of resolving them here?
        Separation of concerns: this class knows about matches and brackets.
        The calendar knows about dates and scheduling. Those two
        responsibilities should not be mixed inside one method.
        """
        if self.current_matchday in self.completed_matchdays:
            return []
        
        current_round_num = self.current_matchday
        # Only consider fixtures that have both teams assigned; placeholders
        # for future rounds may exist with None entries and should be
        # ignored until those slots are filled.
        current_fixtures = [f for f in self.fixtures if f["matchday"] == current_round_num and f.get("home_team") is not None and f.get("away_team") is not None]
        
        drawn_fixtures = []
        
        # ——— Step 1: simulate each match ——————————————————————————————————
        for fixture in current_fixtures:
            home_team = fixture["home_team"]
            away_team = fixture["away_team"]
            
            hg, ag, events, ratings, home_xi, away_xi = simulate_match(
                home_team, away_team,
                max_subs=self.max_subs,
                season_year=self.season_year
            )
            
            self.results.append({
                "home_team": home_team.name,
                "away_team": away_team.name,
                "home_goals": hg,
                "away_goals": ag,
                "events": events,
                "ratings": ratings,
                "home_xi": [xi_entry(p) for p in home_xi],
                "away_xi": [xi_entry(p) for p in away_xi],
                "competition": self.name,
                "season": self.season_year,
                "matchday": current_round_num
            })
            
            if hg == ag:
                drawn_fixtures.append({
                    "home_team": home_team,
                    "away_team": away_team
                })
                
        # ——— Step 2: collect winners (decided matches only) ———————————————————
        winners = []
        for fixture in current_fixtures:
            # Find the matching result by name for this fixture
            result = next(
                (r for r in self.results
                 if r["home_team"] == fixture["home_team"].name
                 and r["away_team"] == fixture["away_team"].name
                 and r.get("matchday") == current_round_num),
                None
            )
            if result is None:
                continue
            if result["home_goals"] > result["away_goals"]:
                winners.append(fixture["home_team"])
            elif result["away_goals"] > result["home_goals"]:
                winners.append(fixture["away_team"])
            # Draws produce no winner yet, bracket slots remain open
            
        # ——— Step 3: Pair decide winners to the next round ———————————————————
        # We only build the next round when we have an even number of winners
        # (i.e. no pending replays). If replays are outstanding the caller
        # must call advance_cup_winner() for each replay result, which will
        # trigger next-round building once all slots are filled.
        if len(winners) > 1 and len(drawn_fixtures) == 0:
            next_round_num = current_round_num + 1
            # Try to fill any placeholder fixtures for the next round first
            placeholders = [f for f in self.fixtures if f["matchday"] == next_round_num and (f.get("home_team") is None or f.get("away_team") is None)]
            if placeholders:
                # Fill placeholders sequentially
                for idx in range(0, len(winners), 2):
                    slot = placeholders[idx // 2]
                    slot["home_team"] = winners[idx]
                    slot["away_team"] = winners[idx + 1]
            else:
                for i in range(0, len(winners), 2):
                    self.fixtures.append({
                        "matchday": next_round_num,
                        "home_team": winners[i],
                        "away_team": winners[i + 1]
                    })
        
        self.completed_matchdays.add(current_round_num)        
        self.current_matchday += 1
        return drawn_fixtures
    
    def advance_cup_winner(self, home_team, away_team, winning_team):
        """
        Called after a replay is simulated to feed the winner into the
        next round of the bracket.
 
        home_team / away_team identify the original drawn fixture.
        winning_team is the Team object that won the replay.
 
        Builds the next round's fixtures once all replay winners are known.
        """
        # Find out which round the original drawn match belonged to so we
        # can work out what the next round number should be
        
        original = next(
            (f for f in self.fixtures
             if f.get("home_team") is not None and f.get("away_team") is not None
             and f["home_team"].name == home_team.name
             and f["away_team"].name == away_team.name),
            None
        )
        if original is None:
            return
        
        original_round = original["matchday"]
        # Next round is the immediate successor round number
        next_round_num = original_round + 1

        # Collect all winners from original round (decided + this replay)
        original_fixtures = [f for f in self.fixtures if f["matchday"] == original_round]
        round_results     = [r for r in self.results if r.get("matchday") == original_round]
        
        winners = []
        
        for fixture in original_fixtures:
            # Is this the just resolved replay?
            if (fixture["home_team"].name == home_team.name
                and fixture["away_team"].name == away_team.name):
                winners.append(winning_team)
                continue
            result = next(
                (r for r in round_results
                 if r["home_team"] == fixture["home_team"].name
                 and r["away_team"] == fixture["away_team"].name),
                None
            )
            if result and result["home_goals"] != result["away_goals"]:
                if result["home_goals"] > result["away_goals"]:
                    winners.append(fixture["home_team"])
                else:
                    winners.append(fixture["away_team"])
                    
        # Only build/fill next round when every slot in this round is decided
        total_slots = len(original_fixtures)
        if len(winners) == total_slots and total_slots > 1:
            # If placeholders were pre-created, fill them; otherwise append
            placeholders = [f for f in self.fixtures if f["matchday"] == next_round_num]
            if placeholders:
                for idx in range(0, len(winners), 2):
                    slot = placeholders[idx // 2]
                    slot["home_team"] = winners[idx]
                    slot["away_team"] = winners[idx + 1]
            else:
                for i in range(0, len(winners), 2):
                    self.fixtures.append({
                        "matchday": next_round_num,
                        "home_team": winners[i],
                        "away_team": winners[i + 1]
                    })
                
    def generate_fixtures(self):
        # Build initial bracket
        teams = self.teams.copy()
        n = len(teams)
        target = self._next_power_of_two(n)
        
        # Add byes as None entries
        while len(teams) < target:
            teams.append(None)
            
        # Create fixtures placeholders for every round so the calendar
        # can schedule cup rounds across the season. Round 1 contains
        # the initial team pairings; later rounds are placeholders
        # (home/away set to None) until winners are filled in.
        import math
        rounds = int(math.log2(target))
        fixtures = []

        # Round 1: pair teams
        round_num = 1
        for i in range(0, len(teams), 2):
            home = teams[i]
            away = teams[i + 1]
            fixtures.append({
                "matchday": round_num,
                "home_team": home,
                "away_team": away
            })

        # Subsequent rounds: create placeholders
        for r in range(2, rounds + 1):
            matches_in_round = target // (2 ** r)
            if matches_in_round < 1:
                matches_in_round = 1
            for _ in range(matches_in_round):
                fixtures.append({
                    "matchday": r,
                    "home_team": None,
                    "away_team": None
                })

        self.fixtures = fixtures