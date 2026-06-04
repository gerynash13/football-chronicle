import random
from simulation import simulate_match
from player_refs import xi_entry, new_competition_id
from rules import get_max_subs, get_points_for_win

class Competition:
    def __init__(self, name, teams, competition_type="league", 
                 max_subs=0, season_year="1896/97", prestige=5000.0):
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
        self.prestige = prestige
        
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


                points_for_win = get_points_for_win(self.season_year)
                
                # Determine result
                if home_goals > away_goals:
                    self.standings[home_team.name]["wins"] += 1
                    self.standings[home_team.name]["points"] += points_for_win
                    self.standings[away_team.name]["losses"] += 1
                elif away_goals > home_goals:
                    self.standings[away_team.name]["wins"] += 1
                    self.standings[away_team.name]["points"] += points_for_win
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
    """
    Round-based knockout cup.

    Each fixture has a 'round' (competition stage: 1, 2, 3...) and a 'winner'
    field set directly when the match is decided. A round is complete when every
    original fixture in it has a winner. Only then is the next round built.

    Replays belong to the same round as the drawn match — they share the same
    'round' number but get a new 'matchday' (calendar slot).
    """
    def __init__(self, name, teams, max_subs=0, season_year="1896/97", prestige=5000.0):
        super().__init__(name, teams, competition_type="cup",
                         max_subs=max_subs, season_year=season_year, prestige=prestige)
        self.current_round = 1
        self._total_rounds = 0
        self._bye_teams = []
        
    @staticmethod
    def _next_power_of_two(n: int) -> int:
        """Returns the next power of two greater than or equal to n."""
        p = 1
        while p < n:
            p *= 2
        return p
    
    # Bracket Generation
    
    def generate_fixtures(self):
        """
        Draw the initial bracket.

        If the team count isn't a power of two, surplus teams receive byes and
        advance automatically to round 2 without playing. Only round 1 is
        generated here — later rounds are built by build_next_round() once
        the previous round is fully resolved.
        """
        import math
        
        teams = self.teams[:]
        random.shuffle(teams)
        
        n = len(teams)
        target = self._next_power_of_two(n)
        byes = target - n
        
        self._total_rounds = int(math.log2(target))
        self._bye_teams = teams[:byes] # Teams that get byes to round 2
        playing = teams[byes:]
        
        self.fixtures = []
        for i in range(0, len(playing), 2):
            self.fixtures.append({
                "round": 1,
                "matchday": 1, # Calendar will assign a real date
                "home_team": playing[i],
                "away_team": playing[i+1],
                "is_replay": False,
                "winner": None,
            })
            
    # Simulation
    
    def simulate_cup_round(self) -> list:
        """
        Simulate all fixtures for self.current_matchday.

        Sets fixture["winner"] directly for decided matches.
        Returns drawn fixture dicts so the engine can schedule replays.
        """
        if self.current_matchday in self.completed_matchdays:
            return []
        
        today = [
            f for f in self.fixtures
            if f["matchday"] == self.current_matchday and f["winner"] is None
        ]
        drawn = []
        
        for fixture in today:
            home, away = fixture["home_team"], fixture["away_team"]
            hg, ag, events, ratings, home_xi, away_xi = simulate_match(
                home, away, max_subs=self.max_subs, season_year=self.season_year
            )
            
            self.results.append({
                "home_team": home.name,
                "away_team": away.name,
                "home_goals": hg,
                "away_goals": ag,
                "events": events,
                "ratings": ratings,
                "home_xi": [xi_entry(p) for p in home_xi],
                "away_xi": [xi_entry(p) for p in away_xi],
                "competition": self.name,
                "season": self.season_year,
                "round": fixture["round"],
                "matchday": self.current_matchday,
            })
            
            if hg > ag:
                fixture["winner"] = home
            elif ag > hg:
                fixture["winner"] = away
            else:
                drawn.append(fixture)
                
        self.completed_matchdays.add(self.current_matchday)
        self.current_matchday += 1
        return drawn
    
    # Replay
    
    def add_replay(self, drawn_fixture: dict, new_matchday: int):
        """
        Register a replay for a drawn match.

        The replay belongs to the SAME round — only the matchday (calendar slot)
        is different. The drawn_fixture itself keeps winner=None until the replay
        decides it, at which point simulate_cup_round sets the winner on the
        REPLAY fixture.

        is_round_complete() checks the original + its replays together.
        """
        self.fixtures.append({
            "round": drawn_fixture["round"],
            "matchday": new_matchday,
            "home_team": drawn_fixture["home_team"],
            "away_team": drawn_fixture["away_team"],
            "is_replay": True,
            "winner": None,
        })
        
    # Round Management
    
    def _get_original_fixtures(self, round_num: int) -> list:
        """Original (non-replay) fixtures for a given round."""
        return [f for f in self.fixtures if f["round"] == round_num and not f.get("is_replay")]
    
    def _get_decided_winner(self, original: dict) -> object | None:
        """
        Return the decided winner for an original fixture, checking replays.

        If the original ended in a draw, look for the most recent replay of
        that same match that has a winner.
        """
        if original["winner"] is not None:
            return original["winner"]
        
        # Find replays for this specific pair, in order of matchday (earliest first)
        replays = [
            f for f in self.fixtures
            if f.get("is_replay")
            and f["round"] == original["round"]
            and f["home_team"].name == original["home_team"].name
            and f["away_team"].name == original["away_team"].name
        ]
        for replay in reversed(replays): # Check latest replay first
            if replay["winner"] is not None:
                return replay["winner"]
            
        return None # No winner decided yet
    
    def is_round_complete(self) -> bool:
        """
        True when every original fixture in the current round has a decided winner
        (either directly or through a replay chain).
        """
        originals = self._get_original_fixtures(self.current_round)
        if not originals:
            return False # No fixtures means we can't say the round is complete
        
        return all(self._get_decided_winner(f) is not None for f in originals)
    
    def build_next_round(self) -> bool:
        """
        If the current round is complete, collect winners and create the next
        round's fixtures. Returns True if a new round was built.

        Called by the engine after each matchday simulation. Safe to call
        multiple times — it does nothing if the round is not yet complete.
        """
        if not self.is_round_complete():
            return False
        
        winners = [
            self._get_decided_winner(f)
            for f in self._get_original_fixtures(self.current_round)
        ]
        
        # Add bye teams after round 1
        if self.current_round == 1 and self._bye_teams:
            winners = winners + self._bye_teams
            random.shuffle(winners) # Shuffle in the bye teams for fairness
            
        if len(winners) <= 1:
            return False # Cup is won - no further rounds needed
        
        next_round = self.current_round + 1
        next_matchday = max(f["matchday"] for f in self.fixtures) + 1
        
        for i in range(0, len(winners), 2):
            self.fixtures.append({
                "round": next_round,
                "matchday": next_matchday,
                "home_team": winners[i],
                "away_team": winners[i+1],
                "is_replay": False,
                "winner": None,
            })
            
        self.current_round = next_round
        return True