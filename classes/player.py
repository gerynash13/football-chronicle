import random
import datetime
from player_refs import new_player_id

PERSONALITY_TRAITS = [
    "ambition",
    "loyalty",
    "professionalism",
    "ego",
    "money_motivation",
    "home_attachment",
    "big_club_attraction",
    "patience",
    "composure",
]

class Player:
    def __init__(self, name, position, birth_date, current_ability,
                 potential_ability, player_id=None,
                 nationality=None, parent_nationality=None,
                 birth_region=None,
                 preferred_foot=None, contract_expires=None, wage=0):

        self.id                 = player_id or new_player_id()
        self.name               = name
        self.position           = position
        self.birth_date         = birth_date
        self.current_ability    = current_ability
        self.potential_ability  = potential_ability

        # Identity
        self.nationality        = nationality
        self.parent_nationality = parent_nationality
        self.birth_region       = birth_region       # region_id string
        self.preferred_foot     = preferred_foot or random.choice(
            ["right", "right", "right", "left", "left", "both"]
        )  # weighted: ~50% right, ~33% left, ~17% both

        # Contract
        self.contract_expires   = contract_expires  # int season start year or None
        self.wage               = wage              # relative integer unit

        # Status
        self.is_retired         = False

        self.attributes         = self._generate_attributes()
        self.role               = self._determine_role()
        self.personality        = self._generate_personality()
        self.morale             = 0.0   # -10 to +10
        self.manager_relationship = 0.0 # -5 to +5

        # Season stats (reset each season)
        self.goals                      = 0
        self.assists                    = 0
        self.appearances                = 0
        self.clean_sheets               = 0
        self.season_avg_rating          = 0.0
        self.season_rating_appearances  = 0
        self.yellow_cards_by_comp       = {}
        self.red_cards                  = 0
        self.is_suspended               = False
        self.suspension_matches_left    = 0
        self.is_injured                 = False
        self.injury_matches_left        = 0
        self.injury_severity            = None  # minor | moderate | severe | critical

        # Career stats (cumulative)
        self.career_goals        = 0
        self.career_assists      = 0
        self.career_appearances  = 0
        self.career_clean_sheets = 0
        self.career_yellow_cards = 0
        self.career_red_cards    = 0
        self.career_injuries     = 0

        # Career history and trophies
        self.career_history          = []
        self.career_trophies         = 0
        self.career_trophies_by_comp = {}
        self._won_trophy_flag        = False

        # Squad number — assigned per season by the engine, not stored permanently.
        # Only used in seasons where competition rules permit squad numbers (post-1928).
        self.squad_number = None

        # Wonderkid flag
        self.is_wonderkid = False

    # ── Derived properties ────────────────────────────────────────────────────
    
    @property
    def yellow_cards(self) -> int:
        """Season total yellow cards, summed across competitions."""
        return sum(self.yellow_cards_by_comp.values())

    def age_on(self, reference_date: datetime.date) -> int:
        """
        Calculate age on a specific date.
        Used during season transitions to update ages accurately.
        
        Why a method rather than a property?
        Age is only meaningful relative to a specific date. A property
        would have to assume "today", which means different things in a
        game running across simulated decades. Passing the date explicitly
        makes the calculation unambiguous.
        
        There is deliberately no plain 'age' property: "now" means the game's 
        date, which only the engine knows, so callers must pass it in.
        """
        bd = self.birth_date
        age = reference_date.year - bd.year
        # If the birthday hasn't occurred yet this year, subtract one
        if (reference_date.month, reference_date.day) < (bd.month, bd.day):
            age -= 1
        return age

    # ── Attributes and role ───────────────────────────────────────────────────

    def _generate_attributes(self):
        if self.position == "FWD":
            return {
                "finishing":   self.current_ability + random.randint(-5, 5),
                "pace":        self.current_ability + random.randint(-5, 5),
                "dribbling":   self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5),
            }
        elif self.position == "MID":
            return {
                "passing":  self.current_ability + random.randint(-5, 5),
                "vision":   self.current_ability + random.randint(-5, 5),
                "stamina":  self.current_ability + random.randint(-5, 5),
                "tackling": self.current_ability + random.randint(-5, 5),
            }
        elif self.position == "DEF":
            return {
                "tackling":    self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5),
                "heading":     self.current_ability + random.randint(-5, 5),
                "pace":        self.current_ability + random.randint(-5, 5),
            }
        elif self.position == "GK":
            return {
                "reflexes":    self.current_ability + random.randint(-5, 5),
                "positioning": self.current_ability + random.randint(-5, 5),
                "handling":    self.current_ability + random.randint(-5, 5),
                "command":     self.current_ability + random.randint(-5, 5),
            }

    def _determine_role(self):
        if self.position == "FWD":
            if (self.attributes["finishing"] + self.attributes["positioning"]
                    > self.attributes["pace"] + self.attributes["dribbling"]):
                return "ST"
            return "W"
        elif self.position == "MID":
            attacking = self.attributes["passing"] + self.attributes["vision"]
            defensive = self.attributes["tackling"] + self.attributes["stamina"]
            if attacking > defensive:
                return "AM"
            elif defensive > attacking:
                return "DM"
            return "CM"
        elif self.position == "DEF":
            if self.attributes["pace"] > self.attributes["heading"] + 5:
                return "FB"
            return "CB"
        elif self.position == "GK":
            return "GK"
        
    def _generate_personality(self):
        """
        Roll this player's personality traits, independent of position or
        ability — a brilliant prospect and a journeyman can be equally
        ambitious. Gaussian around 50 so most players cluster toward the
        middle and extremes near 0 or 100 are rare, same shape as how CA
        gets rolled in name_generator.py.
        """
        return {
            trait: max(0, min(100, int(random.gauss(50, 20))))
            for trait in PERSONALITY_TRAITS
        }

    # ── Season lifecycle ──────────────────────────────────────────────────────

    def end_season(self, season_name, team_name, season_date=None):
        """
        Roll season stats into career totals, save history record, reset.
        
        season_date is used to record the player's age accurately.
        Falls back to birth_date year arithmetic if not provided.
        """
        self.career_goals        += self.goals
        self.career_assists      += self.assists
        self.career_appearances  += self.appearances
        self.career_clean_sheets += self.clean_sheets
        self.career_yellow_cards += self.yellow_cards
        self.career_red_cards    += self.red_cards

        recorded_age = (
            self.age_on(season_date) if season_date
            else int(season_name.split("/")[0]) - self.birth_date.year
        )

        self.career_history.append({
            "season":       season_name,
            "team":         team_name,
            "age":          recorded_age,
            "goals":        self.goals,
            "assists":      self.assists,
            "clean_sheets": self.clean_sheets,
            "yellow_cards": self.yellow_cards,
            "red_cards":    self.red_cards,
            "ca":           self.current_ability,
            "appearances":  self.appearances,
            "squad_number": self.squad_number,
            "kit_color":    None,
            "trophy":       bool(self._won_trophy_flag),
            "avg_rating":   round(self.season_avg_rating, 1)
                            if self.season_rating_appearances > 0 else None,
        })
        self._won_trophy_flag = False

        # Reset season stats
        self.goals                    = 0
        self.assists                  = 0
        self.appearances              = 0
        self.clean_sheets             = 0
        self.yellow_cards_by_comp     = {}
        self.red_cards                = 0
        self.is_suspended             = False
        self.suspension_matches_left  = 0
        self.season_avg_rating        = 0.0
        self.season_rating_appearances = 0

    def start_new_season(self, reference_date: datetime.date):
        """Called at season transition — develops the player."""
        self.develop(reference_date)

    def develop(self, reference_date: datetime.date):
        """
        Apply off-season development, using the player's age on
        reference_date (the game's clock, passed in by the engine).
        """
        age = self.age_on(reference_date)
        ca_change = self._calculate_ca_change(age)
        self.current_ability = max(
            1,
            min(self.current_ability + ca_change, self.potential_ability)
        )
        self.attributes = self._generate_attributes()
        self.role       = self._determine_role()
        
        # Retirement check - players 35+ have an increasing chance to retire
        if age >= 35:
            retire_chance = min(0.8, (age - 34) * 0.15)
            if random.random() < retire_chance:
                self.is_retired = True

    def _calculate_ca_change(self, age: int):
        """
        CA change for the off-season, based on age and room left to grow.
        """
        room_for_growth = self.potential_ability - self.current_ability

        if age <= 20:
            change = random.randint(1, 4)
        elif age <= 23:
            change = random.randint(1, 3)
        elif age <= 27:
            change = random.randint(-1, 2)
        elif age <= 30:
            change = random.randint(-2, 1)
        elif age <= 33:
            change = random.randint(-3, 0)
        else:
            change = random.randint(-4, -1)

        if change > 0:
            change = min(change, room_for_growth)

        return change

    def update_season_rating(self, rating):
        self.season_rating_appearances += 1
        self.season_avg_rating += (
            (rating - self.season_avg_rating) / self.season_rating_appearances
        )
        self.season_avg_rating = round(self.season_avg_rating, 2)