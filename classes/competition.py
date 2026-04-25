import random
from simulation import simulate_match

class Competition:
    def __init__(self, name, teams, competition_type="league"):
        self.name = name
        self.teams = teams
        self.type = competition_type
        self.current_matchday = 1
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
    
    def generate_fixtures(self):
        fixtures_first_half = []
        
        for i, home_team in enumerate(self.teams):
            for away_team in self.teams[i+1:]:
                fixtures_first_half.append({
                    "home_team": home_team,
                    "away_team": away_team
                })
                
        # Distribute across matchdays (6 matches per matchday for 12 teams)
        matches_per_matchday = len(self.teams) // 2
        matchday = 1
        
        for i, fixture in enumerate(fixtures_first_half):
            if i > 0 and i % matches_per_matchday == 0:
                matchday += 1
                
            self.fixtures.append({
                "home_team": fixture["home_team"],
                "away_team": fixture["away_team"],
                "matchday": matchday
            })
        
        # Second half    
        first_half_count = len(fixtures_first_half)
        last_matchday_first_half = matchday
                
        for i in range(first_half_count):
            original_fixture = self.fixtures[i]
            
            second_half_matchday = original_fixture["matchday"] + last_matchday_first_half
            
            self.fixtures.append({
                "home_team": original_fixture["away_team"],
                "away_team": original_fixture["home_team"],
                "matchday": second_half_matchday
            })
            

    def get_current_fixtures(self):
        return [f for f in self.fixtures if f["matchday"] == self.current_matchday]
    
    
    def simulate_matchday(self):
        for fixture in self.fixtures:
            if fixture["matchday"] == self.current_matchday:
                home_team = fixture["home_team"]
                away_team = fixture["away_team"]
                
                home_goals, away_goals = simulate_match(home_team, away_team)
                
                self.results.append({
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_goals": home_goals,
                    "away_goals": away_goals
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
                    self.standings[home_team.name]["points"] += 3
                    self.standings[away_team.name]["losses"] += 1
                elif away_goals > home_goals:
                    self.standings[away_team.name]["wins"] += 1
                    self.standings[away_team.name]["points"] += 3
                    self.standings[home_team.name]["losses"] += 1
                else:
                    self.standings[home_team.name]["draws"] += 1
                    self.standings[home_team.name]["points"] += 1
                    self.standings[away_team.name]["draws"] += 1
                    self.standings[away_team.name]["points"] += 1
                
    def advance_matchday(self):
        input("Do you want to advance to the next matchday? (Press Enter)")
        self.current_matchday += 1
        
    
    def get_standings(self):
        return self.standings