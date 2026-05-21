import random
from player_refs import new_player_id

class Player:
    def __init__(self, name, position, age, current_ability, potential_ability, player_id=None):
        self.id = player_id or new_player_id()
        self.name = name
        self.position = position # GK, DEF, MID, FWD
        self.age = age
        self.current_ability = current_ability
        self.potential_ability = potential_ability
        self.attributes = self._generate_attributes()
        self.role = self._determine_role()
        self.morale = 0.0  # -10 to +10, where 0 is neutral
        self.manager_relationship = 0.0  # -5 to +5, where 0 is neutral

        # Season stats (reset each season)
        self.goals = 0
        self.assists = 0
        self.appearances = 0
        self.clean_sheets = 0
        
        self.season_avg_rating = 0.0
        self.season_rating_appearances = 0
        
        self.yellow_cards = 0
        self.red_cards = 0
        self.is_suspended = False
        self.suspension_matches_left = 0
        
        self.is_injured = False
        self.injury_matches_left = 0
        self.injury_severity = None  # "minor" | "moderate" | "severe" | "critical"
        
        # Career stats (cumulative)
        self.career_goals = 0
        self.career_assists = 0
        self.career_appearances = 0
        self.career_clean_sheets = 0
        
        self.career_yellow_cards = 0
        self.career_red_cards = 0
        self.career_injuries = 0
        
        # Career history (list of season records)
        self.career_history = []
        self.career_trophies = 0
        self.career_trophies_by_comp = {}
        # Squad number (may be assigned when squad is generated)
        self.squad_number = None
        # Temporary flag set when player wins a trophy this season
        self._won_trophy_flag = False
        
        # Wonderkid flag (for potential future use in scouting, etc.)
        self.is_wonderkid = False

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
        
    def end_season(self, season_name, team_name):
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
        self.career_clean_sheets += self.clean_sheets
        self.career_yellow_cards += self.yellow_cards
        self.career_red_cards += self.red_cards
        
        # Save season record
        self.career_history.append({
            "season": season_name,
            "team": team_name,
            "goals": self.goals,
            "assists": self.assists,
            "clean_sheets": self.clean_sheets,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "ca": self.current_ability,
            "appearances": self.appearances,
            "age": self.age,
            "squad_number": self.squad_number,
            "kit_color": None,    # Hex primary color, set on Team later
            "trophy": bool(self._won_trophy_flag),
            "avg_rating": round(self.season_avg_rating, 1) if self.season_rating_appearances > 0 else None
        })
        # Clear seasonal trophy flag after recording
        self._won_trophy_flag = False
        
        # Reset season stats
        self.goals = 0
        self.assists = 0
        self.appearances = 0
        self.clean_sheets = 0
        self.yellow_cards = 0
        self.red_cards = 0
        self.is_suspended = False
        self.suspension_matches_left = 0
        self.season_avg_rating = 0.0
        self.season_rating_appearances = 0
        
    def start_new_season(self):
        # Called before each season - ages the player and updates their ability
        self.develop()
        
    def develop(self):
        # Age the player
        self.age += 1
        ca_change = self._calculate_ca_change()
        
        # Apply change, keeping within 1 and potential ability limits
        self.current_ability = max(1, min(self.current_ability + ca_change, self.potential_ability + ca_change))
        
        # Update attributes and role based on new CA
        self.attributes = self._generate_attributes()
        self.role = self._determine_role()
        
    def _calculate_ca_change(self):
        """
        Returns the CA change for this off-season.
        Growth is capped by how much room the player has left to reach its PA
        """
        room_for_growth = self.potential_ability - self.current_ability
        
        if self.age <= 20:
            change = random.randint(1, 4)
        elif self.age <= 23:
            change = random.randint(1, 3)
        elif self.age <= 27:
            change = random.randint(-1, 2)
        elif self.age <= 30:
            change = random.randint(-2, 1)
        elif self.age <= 33:
            change = random.randint(-3, 0)
        else:
            change = random.randint(-4, -1)
            
        # Can't grow beyond PA
        if change > 0:
            change = min(change, room_for_growth)
            
        return change
    
    def update_season_rating(self, rating):
        # Update the player's average rating for the season
        self.season_rating_appearances += 1
        self.season_avg_rating += ((rating - self.season_avg_rating) / self.season_rating_appearances)
        self.season_avg_rating = round(self.season_avg_rating, 2)