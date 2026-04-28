import random

class Team:
    def __init__(self, name, attack, midfield, defense):
        self.name = name
        self.attack = attack
        self.midfield = midfield
        self.defense = defense
        self.squad = []

    def add_player(self, player):
        self.squad.append(player)
        
    def get_strength(self):
        return (self.attack + self.midfield + self.defense) / 3
    
    def select_starting_xi(self, opponent_strength=None, rotation_chance=0.1):
        formation = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 5}
        starting_xi = []
        
        for position, count in formation.items():
            # Get all the players in this position
            position_players = [p for p in self.squad if p.position == position]
            
            # Sort by CA with randomness
            # Add random variance
            position_players.sort(
                key=lambda p: p.current_ability + random.randint(-5, 5),
                reverse=True
            )
            
            # Select top n players for position
            selected = position_players[:count]
            starting_xi.extend(selected)
            
        return starting_xi