from rng import rng
from simulation import simulate_match, pick_player_for_chance, pick_assister
from player_refs import xi_entry, new_competition_id, goal_refs
from rules import get_max_subs, get_points_for_win

class Competition:
    def __init__(self, name, teams, competition_type="league", 
                 max_subs=0, season_year="1896/97", prestige=5000.0):
        self.id = new_competition_id()
        self.name = name
        self.teams = teams
        self.type = competition_type
        self.current_matchday = 1
        self.fixtures = []
        self.results = []
        self.standings = self.initialize_standings()
        self.completed_matchdays = set()
        self.max_subs = max_subs
        self.season_year = season_year
        self.prestige = prestige
        self.key = None
        self.tier = None # 1 = top flight (leagues only)
        self.nation_id = None
        
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
        n = len(self.teams)
        
        # For round-robin, we need an even amount of teams
        # If not even, add a bye (None)
        teams = self.teams.copy()
        if n % 2 == 1:
            teams.append(None)
            n += 1
            
        fixtures = []
        
        # Generate first half of the season
        for round_num in range(n - 1):
            for i in range(n // 2):
                home = teams[i]
                away = teams[n - 1 - i]
                
                if home is not None and away is not None:
                    fixtures.append({
                        "matchday": round_num + 1,
                        "home_team": home,
                        "away_team": away
                    })
                
            # Rotate teams (keep first team fixed)
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    
        # Store first half of fixtures
        self.fixtures = fixtures.copy()
        
        # Generate second half of fixtures
        last_matchday = n - 1
        for fixture in fixtures:
            self.fixtures.append({
                "matchday": fixture["matchday"] + last_matchday,
                "home_team": fixture["away_team"],
                "away_team": fixture["home_team"]
            })

    def get_current_fixtures(self):
        return [f for f in self.fixtures if f["matchday"] == self.current_matchday]
    
    def _apply_match_cards(self, result: dict) -> None:
        """
        Walk a finished match's events for bookings and file them under this
        competition's bucket. Called once per match, right after the result
        is recorded.
        """
        from player_refs import find_player
        from rules import get_card_bucket

        bucket = get_card_bucket(self.name)
        for evt in result.get("events", []):
            if evt["type"] != "yellow_card":
                continue
            player, _ = find_player(
                self.teams,
                player_id=evt.get("player_id"),
                name=evt.get("player"),
                team_name=evt.get("team"),
            )
            if player:
                player.yellow_cards_by_comp[bucket] = (
                    player.yellow_cards_by_comp.get(bucket, 0) + 1
                )
    
    def simulate_matchday(self):
        # Check if matchday has already been simulated
        if self.current_matchday in self.completed_matchdays:
            return
        
        # Simulate matches
        for fixture in self.fixtures:
            if fixture["matchday"] == self.current_matchday:
                home_team = fixture["home_team"]
                away_team = fixture["away_team"]
                
                home_goals, away_goals, events, ratings, home_xi, away_xi = simulate_match(
                    home_team, away_team, max_subs=self.max_subs, season_year=self.season_year
                )
                
                result = {
                    "home_team": home_team.name,
                    "away_team": away_team.name,
                    "home_team_id": home_team.id,
                    "away_team_id": away_team.id,
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "events": events,
                    "ratings": ratings,
                    "home_xi": [xi_entry(p) for p in home_xi],
                    "away_xi": [xi_entry(p) for p in away_xi],
                    "competition": self.name,
                    "season": self.season_year,
                }
                self.results.append(result)
                self._apply_match_cards(result)
                
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


                points_for_win = get_points_for_win(self.season_year)
                
                # Determine result
                if home_goals > away_goals:
                    self.standings[home_team.name]["wins"] += 1
                    self.standings[home_team.name]["points"] += points_for_win
                    self.standings[away_team.name]["losses"] += 1
                elif away_goals > home_goals:
                    self.standings[away_team.name]["wins"] += 1
                    self.standings[away_team.name]["points"] += points_for_win
                    self.standings[home_team.name]["losses"] += 1
                else:
                    self.standings[home_team.name]["draws"] += 1
                    self.standings[home_team.name]["points"] += 1
                    self.standings[away_team.name]["draws"] += 1
                    self.standings[away_team.name]["points"] += 1
        
        # Mark matchday as completed            
        self.completed_matchdays.add(self.current_matchday)
                
    def advance_matchday(self):
        # Non-interactive environment: simply advance the matchday counter.
        # Removed blocking input() so the engine can run headless (API/web).
        self.current_matchday += 1
        
    
    def get_standings(self):
        return self.standings

    @property
    def total_rounds(self):
        """Total rounds/matchdays in the competition"""
        if not self.fixtures:
            return 0
        return max(f["matchday"] for f in self.fixtures)


class CupCompetition(Competition):
    """
    Round-based knockout cup.

    Each fixture has a 'round' (competition stage: 1, 2, 3...) and a 'winner'
    field set directly when the match is decided. A round is complete when every
    original fixture in it has a winner. Only then is the next round built.

    Replays belong to the same round as the drawn match — they share the same
    'round' number but get a new 'matchday' (calendar slot).
    """
    def __init__(self, name, teams, max_subs=0, season_year="1896/97", prestige=5000.0):
        super().__init__(name, teams, competition_type="cup",
                         max_subs=max_subs, season_year=season_year, prestige=prestige)
        self.current_round = 1
        self._total_rounds = 0
        self._bye_teams = []
        
    @staticmethod
    def _next_power_of_two(n: int) -> int:
        """Returns the next power of two greater than or equal to n."""
        p = 1
        while p < n:
            p *= 2
        return p
    
    # Bracket Generation
    
    def generate_fixtures(self):
        """
        Draw the initial bracket.

        If the team count isn't a power of two, surplus teams receive byes and
        advance automatically to round 2 without playing. Only round 1 is
        generated here — later rounds are built by build_next_round() once
        the previous round is fully resolved.
        """
        import math
        
        teams = self.teams[:]
        rng.shuffle(teams)
        
        n = len(teams)
        target = self._next_power_of_two(n)
        byes = target - n
        
        self._total_rounds = int(math.log2(target))
        self._bye_teams = teams[:byes] # Teams that get byes to round 2
        playing = teams[byes:]
        
        self.fixtures = []
        for i in range(0, len(playing), 2):
            self.fixtures.append({
                "round": 1,
                "matchday": 1, # Calendar will assign a real date
                "home_team": playing[i],
                "away_team": playing[i+1],
                "is_replay": False,
                "winner": None,
            })
            
    # Simulation
    
    def simulate_cup_round(self) -> list:
        """
        Simulate all fixtures for self.current_matchday.

        Sets fixture["winner"] directly for decided matches.
        Returns drawn fixture dicts so the engine can schedule replays.
        """
        if self.current_matchday in self.completed_matchdays:
            return []
        
        today = [
            f for f in self.fixtures
            if f["matchday"] == self.current_matchday and f["winner"] is None
        ]
        drawn = []
        
        for fixture in today:
            home, away = fixture["home_team"], fixture["away_team"]
            hg, ag, events, ratings, home_xi, away_xi = simulate_match(
                home, away, max_subs=self.max_subs, season_year=self.season_year
            )
            
            result = {
                "home_team": home.name,
                "away_team": away.name,
                "home_team_id": home.id,
                "away_team_id": away.id,
                "home_goals": hg,
                "away_goals": ag,
                "events": events,
                "ratings": ratings,
                "home_xi": [xi_entry(p) for p in home_xi],
                "away_xi": [xi_entry(p) for p in away_xi],
                "competition": self.name,
                "season": self.season_year,
                "round": fixture["round"],
                "matchday": self.current_matchday,
            }
            self.results.append(result)
            self._apply_match_cards(result)
            
            if hg > ag:
                fixture["winner"] = home
            elif ag > hg:
                fixture["winner"] = away
            else:
                drawn.append(fixture)
                
        self.completed_matchdays.add(self.current_matchday)
        self.current_matchday += 1
        return drawn
    
    # Replay
    
    def add_replay(self, drawn_fixture: dict, new_matchday: int):
        """
        Register a replay for a drawn match.

        The replay belongs to the SAME round — only the matchday (calendar slot)
        is different. The drawn_fixture itself keeps winner=None until the replay
        decides it, at which point simulate_cup_round sets the winner on the
        REPLAY fixture.

        is_round_complete() checks the original + its replays together.
        """
        self.fixtures.append({
            "round": drawn_fixture["round"],
            "matchday": new_matchday,
            "home_team": drawn_fixture["home_team"],
            "away_team": drawn_fixture["away_team"],
            "is_replay": True,
            "winner": None,
        })
        
    # Round Management
    
    def _get_original_fixtures(self, round_num: int) -> list:
        """Original (non-replay) fixtures for a given round."""
        return [f for f in self.fixtures if f["round"] == round_num and not f.get("is_replay")]
    
    def _get_decided_winner(self, original: dict) -> object | None:
        """
        Return the decided winner for an original fixture, checking replays.

        If the original ended in a draw, look for the most recent replay of
        that same match that has a winner.
        """
        if original["winner"] is not None:
            return original["winner"]
        
        # Find replays for this specific pair, in order of matchday (earliest first)
        replays = [
            f for f in self.fixtures
            if f.get("is_replay")
            and f["round"] == original["round"]
            and f["home_team"].name == original["home_team"].name
            and f["away_team"].name == original["away_team"].name
        ]
        for replay in reversed(replays): # Check latest replay first
            if replay["winner"] is not None:
                return replay["winner"]
            
        return None # No winner decided yet
    
    def is_round_complete(self) -> bool:
        """
        True when every original fixture in the current round has a decided winner
        (either directly or through a replay chain).
        """
        originals = self._get_original_fixtures(self.current_round)
        if not originals:
            return False # No fixtures means we can't say the round is complete
        
        return all(self._get_decided_winner(f) is not None for f in originals)
    
    def build_next_round(self) -> bool:
        """
        If the current round is complete, collect winners and create the next
        round's fixtures. Returns True if a new round was built.

        Called by the engine after each matchday simulation. Safe to call
        multiple times — it does nothing if the round is not yet complete.
        """
        if not self.is_round_complete():
            return False
        
        winners = [
            self._get_decided_winner(f)
            for f in self._get_original_fixtures(self.current_round)
        ]
        
        # Add bye teams after round 1
        if self.current_round == 1 and self._bye_teams:
            winners = winners + self._bye_teams
            rng.shuffle(winners) # Shuffle in the bye teams for fairness
            
        if len(winners) <= 1:
            return False # Cup is won - no further rounds needed
        
        next_round = self.current_round + 1
        next_matchday = max(f["matchday"] for f in self.fixtures) + 1
        
        for i in range(0, len(winners), 2):
            self.fixtures.append({
                "round": next_round,
                "matchday": next_matchday,
                "home_team": winners[i],
                "away_team": winners[i+1],
                "is_replay": False,
                "winner": None,
            })
            
        self.current_round = next_round
        return True
    
class SupercupCompetition(Competition):
    """
    Single-match (or two-leg) competition between exactly two pre-determined
    teams — typically the league winner vs the cup winner.
 
    Unlike CupCompetition, there is not always a bracket and rounds to build.
    The fixture is created directly from the participants at construction
    time and the result is decided in one session.
 
    Draw resolution is entirely driven by the draw_rules dict read from
    competitions.yaml, so behaviour can differ between nations without
    touching any Python code:
 
        draw_rules:
            extra_time: true   → simulate a 30-minute extra-time period
            penalties:  true   → penalty shootout if still level
            replay:     true   → return the draw to the engine to reschedule
 
    Only one of penalties / replay should be true.  extra_time only applies
    when penalties is also true.
    """
    
    def __init__(self, name, teams, draw_rules=None,
                 max_subs=0, season_year="1896/97", prestige=4000.0):
        super().__init__(name, teams, competition_type="supercup", max_subs=max_subs,
                         season_year=season_year, prestige=prestige)
        
        # draw_rules comes from CompetitionConfig.draw_rules (YAML)
        # Default: straight to penalties, no extra time, no replay
        self.draw_rules = draw_rules or {"extra_time": False, "penalties": True, "replay": False}
        
    # Fixture generation
    
    def generate_fixtures(self):
        """
        Create the single fixture.  The calendar will assign a real date later.
        Teams must be exactly two objects; this is enforced by the engine before
        calling generate_fixtures().
        """
        if len(self.teams) != 2:
            raise ValueError(f"Supercup must have exactly two teams, got {len(self.teams)}")
        
        self.fixtures = [{
            "matchday": 1,
            "home_team": home,
            "away_team": away,
            "winner": None,
            "decided_in": None,
        }]
        
    # Simulation
    
    def simulate_supercup(self) -> dict | None:
        """
        Simulate the supercup fixture, applying draw_rules if the match is level.
 
        Returns the drawn fixture dict if a REPLAY is required (so the engine
        can schedule it), or None if the result was fully decided here.
 
        Sets fixture["winner"] and fixture["decided_in"] when a winner is found.
        Records the full result (including any ET / penalty events) in
        self.results.
 
        Why return the fixture rather than a boolean?
        The engine's replay machinery already accepts a fixture dict from
        CupCompetition — keeping the same interface means the same calendar
        scheduling code can handle supercup replays without modification.
        """
        if self.current_matchday in self.completed_matchdays:
            return None # Already decided
        
        fixture = next(
            (f for f in self.fixtures
             if f["matchday"] == self.current_matchday and f["winner"] is None),
            None,
        )
        if fixture is None:
            return None # No fixture to simulate
        
        home, away = fixture["home_team"], fixture["away_team"]
        hg, ag, events, ratings, home_xi, away_xi = simulate_match(
            home, away, max_subs=self.max_subs, season_year=self.season_year
        )
        
        decided_in = "normal"
        
        # Draw resolution
        if hg == ag:
            if self.draw_rules.get("extra_time"):
                et_hg, et_ag, et_events = self._simulate_extra_time(home, away)
                hg += et_hg
                ag += et_ag
                events += et_events
                if hg != ag:
                    decided_in = "extra_time"
                    
            if hg == ag and self.draw_rules.get("penalties"):
                pk_winner, pk_events = self._simulate_penalty_shootout(home, away)
                events += pk_events
                fixture["winner"] = pk_winner
                decided_in = "penalties"
                
            elif hg == ag and self.draw_rules.get("replay"):
                self.results.append(self._build_result(
                    fixture, home, away, hg, ag, events, ratings, home_xi, away_xi,
                    decided_in="draw",
                ))
                self.completed_matchdays.add(self.current_matchday)
                self.current_matchday += 1
                return fixture # Engine will call schedule_replay()
            
        # Winner decided by score (or already set by penalties above)
        if fixture["winner"] is None:
            fixture["winner"] = home if hg > ag else away
        fixture["decided_in"] = decided_in
        
        self.results.append(self._build_result(
            fixture, home, away, hg, ag, events, ratings, home_xi, away_xi,
            decided_in=decided_in,
        ))
        
        self.completed_matchdays.add(self.current_matchday)
        self.current_matchday += 1
        return None # Fully decided, no replay needed
    
    # Extra time
    
    def _simulate_extra_time(self, home, away) -> tuple[int, int, list]:
        """
        Simulate a 30-minute extra-time period (two 15-minute halves).
 
        Uses a reduced chance count — roughly 30% of a normal 90-minute match.
        Returns (home_goals, away_goals, events_list).
 
        Why not call simulate_match() again?
        simulate_match() always runs 90 minutes and updates player stats
        (appearances, injuries, suspensions).  Extra time is a continuation of
        the same match — we don't want to double-count appearances.  This
        stripped-down version generates chances only, keeping stat side-effects
        to goals and assists.
        """
        et_hg = et_ag = 0
        et_events = []
        
        base_chances = 10
        midfield_bonus = (home.midfield + away.midfield) // 20
        total_chances = int(base_chances + midfield_bonus + rng.randint(-2, 2))
        chance_minutes = sorted(
            [rng.randint(91, 120) for _ in range(total_chances)],
        )
        
        home_xi = home.select_starting_xi(opponent_strength=away.get_strength())
        away_xi = away.select_starting_xi(opponent_strength=home.get_strength())
        
        for minute in chance_minutes:
            h_power = home.midfield ** 4
            a_power = away.midfield ** 4
            if rng.random() < h_power / (h_power + a_power):
                shot_quality = home.attack - away.defense
                chance = max(8, min(shot_quality / 2 + home.attack / 30, 40))
                if rng.randint(1, 100) < chance:
                    et_hg += 1
                    scorer = pick_player_for_chance(home_xi)
                    scorer.goals += 1
                    assister = pick_assister(home_xi, scorer)
                    if assister:
                        assister.assists += 1
                    et_events.append({
                        "minute": minute,
                        "team": home.name,
                        "type": "goal",
                        **goal_refs(scorer, assister),
                        "period": "extra_time",
                    })
                    
            else:
                shot_quality = away.attack - home.defense
                chance = max(8, min(shot_quality / 2 + away.attack / 30, 40))
                if rng.randint(1, 100) < chance:
                    et_ag += 1
                    scorer = pick_player_for_chance(away_xi)
                    scorer.goals += 1
                    assister = pick_assister(away_xi, scorer)
                    if assister:
                        assister.assists += 1
                    et_events.append({
                        "minute": minute,
                        "team": away.name,
                        "type": "goal",
                        **goal_refs(scorer, assister),
                        "period": "extra_time",
                    })
                    
        return et_hg, et_ag, et_events
    
    # Penalty shootout
    
    def _simulate_penalty_shootout(self, home, away) -> tuple[object, list]:
        """
        Simulate a penalty shootout.
 
        Each team takes up to 5 penalties; if still level after 5 rounds,
        sudden death continues until someone misses while the other scores.
        GK ability (reflexes attribute) lowers the base conversion rate slightly.
 
        Returns (winning_team_object, events_list).
 
        The events list carries one dict per kick so the frontend can render a
        full shootout sequence if it wants to, but it is also perfectly fine to
        just read the winner and ignore the individual kicks.
        """
        home_gk = next(
            (p for p in home.squad if p.position == "GK"), None
        )
        away_gk = next(
            (p for p in away.squad if p.position == "GK"), None
        )
        
        # Base conversion rate; GK reflexes slightly reduces it
        def _conversion(gk) -> float:
            if gk is None:
                return 0.75
            reflexes = gk.attributes.get("reflexes", gk.current_ability)
            # Every 10 points of reflexes above 50 reduces conversion by ~1%
            return max(0.55, 0.75 - (max(reflexes - 50, 0) / 1000))
        
        home_conv = _conversion(away_gk)
        away_conv = _conversion(home_gk)
        
        home_goals = away_goals = 0
        events = []
        round_num = 0
        
        while True:
            round_num += 1
            # After round 5, switch to sudden death
            for team, conv, gk, label in (
                (home, home_conv, away_gk, "home"),
                (away, away_conv, home_gk, "away"),
            ):
                scored = rng.random() < conv
                if scored:
                    if label == "home":
                        home_goals += 1
                    else:
                        away_goals += 1
                        
                events.append({
                    "type": "penalty_kick",
                    "team": team.name,
                    "round": round_num,
                    "scored": scored,
                    "period": "penalties",
                })
                
            # After 5 rounds, whoever leads wins
            if round_num >= 5 and home_goals != away_goals:
                break
            if round_num > 5 and home_goals != away_goals:
                break
            # Safety valve
            if round_num > 30:
                break
            
        winner = home if home_goals > away_goals else away
        events.append({
            "type": "penalty_result",
            "home_team": home.name,
            "away_team": away.name,
            "home_penalties": home_goals,
            "away_penalties": away_goals,
            "winner": winner.name,
            "period": "penalties",
        })
        return winner, events
    
    # Result builder
    
    @staticmethod
    def _build_result(fixture, home, away, hg, ag, events, ratings,
                      home_xi, away_xi, decided_in="normal") -> dict:
        return {
            "home_team": home.name,
            "away_team": away.name,
            "home_team_id": home.id,
            "away_team_id": away.id,
            "home_goals": hg,
            "away_goals": ag,
            "events": events,
            "ratings": ratings,
            "home_xi": [xi_entry(p) for p in home_xi],
            "away_xi": [xi_entry(p) for p in away_xi],
            "competition": fixture.get("competition", ""),
            "season": fixture.get("season", ""),
            "decided_in": decided_in,
            "winner": fixture["winner"].name if fixture.get("winner") else None,
        }