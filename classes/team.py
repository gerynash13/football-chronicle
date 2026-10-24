from rng import rng
from player_refs import new_team_id
from strength import FORMATION
from facilities import DEFAULT_FACILITIES
from classes.player import Player

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
        self.retired = []
        self.facilities = dict(DEFAULT_FACILITIES)
        self.youth = []  # Academy players
        self.released = []  # Let go from the academy
        self.competitions = []  # ids of the competitions this team is in

    def add_player(self, player):
        self.squad.append(player)
        
    def get_strength(self):
        base = (self.attack + self.midfield + self.defense) / 3
        return base + (self.morale * 0.3)  # Morale can boost or reduce strength by up to 3 points
    
    def select_starting_xi(self, opponent_strength=None, rotation_chance=0.1):
        for p in self.squad:
            p.playing_as = None
        available = [p for p in self.squad
                     if not (p.is_injured or p.is_suspended or p.is_retired)]
        xi, shortfall = [], []
        for position, count in FORMATION.items():
            pool = sorted((p for p in available if p.position == position),
                          key=lambda p: p.current_ability + p.morale + rng.randint(-3, 3),
                          reverse=True)
            picked = pool[:count]
            for p in picked:
                p.playing_as = position
            xi.extend(picked)
            shortfall.extend([position] * (count - len(picked)))
        # Emergencies: fill empty slots with the best remaining players
        leftovers = sorted((p for p in available if p not in xi),
                           key=lambda p: p.current_ability, reverse=True)
        for position in shortfall:
            if not leftovers:
                break
            p = leftovers.pop(0)
            p.playing_as = position
            xi.append(p)
        return xi