import random

class Team:
    def __init__(self, name, attack, midfield, defense):
        self.name = name
        self.attack = attack
        self.midfield = midfield
        self.defense = defense
        self.squad = []

    def _add_player(self, player):
        self.squad.append(player)