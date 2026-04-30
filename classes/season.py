class Season:
    def __init__(self, year, teams):
        self.year = year
        self.teams = teams
        self.competitions = []
        self.is_complete = False
        
    def add_competition(self, competition):
        self.competitions.append(competition)
        
    def end_season(self):
        """
        We call this function when a season is complete to:
        1. Finalize all player stats
        2. Save season records
        3. Mark as complete
        """
        
        for team in self.teams:
            for player in team.squad:
                player.end_season(self.year, team.name)
                
        self.is_complete = True
        print(f"\n{'='*80}")
        print(f"Season {self.year} completed!")
        print(f"{'='*80}\n")