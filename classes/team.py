from rng import rng
from player_refs import new_team_id

class Team:
    def __init__(self, name, attack, midfield, defense):
        self.id = new_team_id()
        self.name = name
        self.nation_id = ""  # To be set when team is assigned to a nation
        self.league_nation_id = ""
        self.league_nation_id_year = None
        self.attack = attack
        self.midfield = midfield
        self.defense = defense
        self.squad = []
        self.morale = 0.0  # -10 to +10, where 0 is neutral
        self.board_confidence = 50.0  # 0 to 100
        self.fan_satisfaction = 50.0  # 0 to 100
        self.trophies = []
        self.prestige = 500.0
        self.home_region = ""
        self.budget = 1000
        self.wage_budget = 300

    def add_player(self, player):
        self.squad.append(player)
        
    def get_strength(self):
        base = (self.attack + self.midfield + self.defense) / 3
        return base + (self.morale * 0.3)  # Morale can boost or reduce strength by up to 3 points
    
    def select_starting_xi(self, opponent_strength=None, rotation_chance=0.1):
        formation = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 5}
        starting_xi = []
        
        for position, count in formation.items():
            # Get all the players in this position
            position_players = [
                p for p in self.squad 
                if p.position == position
                and not p.is_injured
                and not p.is_suspended
            ]
            
            # Sort by CA with randomness
            # Add random variance
            position_players.sort(
                key=lambda p: p.current_ability + p.morale + rng.randint(-3, 3),
                reverse=True
            )
            
            # Select top n players for position
            selected = position_players[:count]
            starting_xi.extend(selected)
            
        return starting_xi