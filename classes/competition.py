import random
from simulation import simulate_match

class Competition:
    def __init__(self, name, teams, competition_type="league"):
        self.name = name
        self.teams = teams
        self.type = competition_type
        self.current_matchday = 0
        self.fixtures = []
        self.results = []
        self.standings = self.initialize_standings()
        
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