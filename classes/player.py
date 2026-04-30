import random

class Player:
    def __init__(self, name, position, age, current_ability, potential_ability):
        self.name = name
        self.position = position # GK, DEF, MID, FWD
        self.age = age
        self.current_ability = current_ability
        self.potential_ability = potential_ability
        self.attributes = self._generate_attributes()
        self.role = self._determine_role()

        # Season stats (reset each season)
        self.goals = 0
        self.assists = 0
        self.appearances = 0
        
        # Career stats (cumulative)
        self.career_goals = 0
        self.career_assists = 0
        self.career_appearances = 0
        
        # Career history (list of season records)
        self.career_history = []

    def _generate_attributes(self):
        if self.position == "FWD":
            return {
                "finishing": self.current_ability + random.randint(-5, 5),
                "pace": self.current_ability + random.randint(-5, 5),
                "dribbling": self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5)
            }

        elif self.position == "MID":
            return {
                "passing": self.current_ability + random.randint(-5, 5),
                "vision": self.current_ability + random.randint(-5, 5),
                "stamina": self.current_ability + random.randint(-5, 5),
                "tackling": self.current_ability + random.randint(-5, 5)
            }

        elif self.position == "DEF":
            return {
                "tackling": self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5),
                "heading": self.current_ability + random.randint(-5, 5),
                "pace": self.current_ability + random.randint(-5, 5)
            }

        elif self.position == "GK":
            return {
                "reflexes": self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5),
                "handling": self.current_ability + random.randint(-5, 5),
                "command": self.current_ability + random.randint(-5, 5)
            }

    def _determine_role(self):
        if self.position == "FWD":
            # Striker --> High Finishing and Positioning
            # Winger --> High Pace and Dribbling
            if self.attributes["finishing"] + self.attributes["positioning"] > self.attributes["pace"] + self.attributes["dribbling"]:
                return "ST"
            else:
                return "W"

        elif self.position == "MID":
            attacking = self.attributes["passing"] + self.attributes["vision"]
            defensive = self.attributes["tackling"] + self.attributes["stamina"]

            if attacking > defensive:
                return "AM"

            elif defensive > attacking:
                return "DM"

            else:
                return "CM"

        elif self.position == "DEF":
            # If pace quite higher than heading --> FB
            if self.attributes["pace"] > self.attributes["heading"] + 5:
                return "FB"
            else:
                return "CB"
        
        elif self.position == "GK":
            return "GK"
        
    def end_season(self):
        """
        We use this function at the end of the season to:
        1. Add season state to career totals
        2. Save season record to history
        3. Reset season stats
        """
        
        # Add to career totals
        self.career_goals += self.goals
        self.career_assists += self.assists
        self.career_appearances += self.appearances
        
        # Save season record
        self.career_history.append({
            "season": season_name,
            "team": team_name,
            "goals": self.goals,
            "assists": self.assists,
            "appearances": self.appearances,
            "age": self.age
        })
        
        # Reset season stats
        self.goals = 0
        self.assists = 0
        self.appearances = 0
        
    def start_new_season(self):
        # This function is for future features (fitness, form, etc.)
        pass