"""
prestige.py — Season-end prestige update system

Prestige updates happen in three stages each season:
    1. Decay   — everyone loses a fixed fraction of their prestige
    2. Awards  — competition performance earns prestige back
    3. Floor   — prestige never drops below the configured minimum

Team prestige and nation prestige update independently.
Nation prestige is pulled toward its clubs' collective performance.

UPSET MULTIPLIER
When a lower-prestige team beats a higher-prestige one, the winner
earns a bonus proportional to the gap. Bonuses accumulate across the
full season and are applied at season end alongside position awards.

TIER CHANGE GUARD
A nation's tier (derived from prestige) only commits after
tier_change_min_seasons consecutive seasons at the new level.
This prevents a single unusual season from immediately changing
the PA caps used for player generation.
The guard state is owned by the engine and persisted in world_state.json.

CALLING ORDER (from engine._advance_between_seasons):
    bonuses    = collect_upset_bonuses(self.comp.results, self.teams)
    team_log   = update_team_prestige(self.teams, standings, self.comp.prestige, bonuses)
    nation_log = update_nation_prestige(nations, self.teams, standings,
                                        self.comp.prestige,
                                        self._tier_seasons,
                                        self._committed_tiers)
"""

from __future__ import annotations
from data_loader import prestige_to_tier

# CONSTANTS
TEAM_DECAY_RATE = 0.05 
TEAM_PRESTIGE_FLOOR = 100.0

# Upset bonus

def collect_upset_bonuses(results: list[dict], teams) -> dict[str, float]:
    """
    Scan all completed match results and return accumulated upset bonuses.

    An upset is when the lower-prestige team wins. The bonus scales with
    the prestige gap so a true giant-killing earns more than a marginal win.
    Capped at 80 points per match so no single result dominates.

    Returns {team_name: total_bonus}.
    """
    team_map = {t.name: t for t in teams}
    bonuses: dict[str, float] = {}
    
    for result in results:
        home = team_map.get(result["home_team"])
        away = team_map.get(result["away_team"])
        if not home or not away:
            continue
        
        hg, ag = result["home_goals"], result["away_goals"]
        # Positive gap = home team is the stronger team
        gap = home.prestige - away.prestige
        
        if ag > hg and gap > 50:
            # Underdog away win
            bonus = min(gap * 0.08, 80.0)
            bonuses[away.name] = bonuses.get(away.name, 0.0) + bonus
        elif hg > ag and gap < -50:
            # Underdog home win
            bonus = min(abs(gap) * 0.08, 80.0)
            bonuses[home.name] = bonuses.get(home.name, 0.0) + bonus
            
    return bonuses

# Position award

def _position_award(position: int, total_teams: int, comp_prestige: float) -> float:
    """
    Award prestige for finishing at a given league position.

    Uses a triangular weight distribution:
        1st place → weight n, 2nd → n-1, ..., last → 1

    The total pool is 40% of comp_prestige, split across all teams.
    Crucially, even last place earns something — this means every team
    participates in the prestige economy and none free-falls in isolation.

    Example (12 teams, comp_prestige=5000, pool=2000):
        1st: ~308  |  6th: ~179  |  12th: ~26
    """
    pool            = comp_prestige * 0.4
    total_weight    = total_teams * (total_teams + 1) / 2
    weight          = total_teams - position + 1
    return pool * (weight / total_weight)

# Team prestige update

def update_team_prestige(
    teams,
    standings: list[dict],
    comp_prestige: float,
    upset_bonuses: dict[str, float] | None= None,
) -> list[dict]:
    """
    Apply the three prestige stages to every team in the competition.

    standings     : serialized standings list from engine._serialize_standings()
    comp_prestige : the competition's prestige value (stored on the Competition object)
    upset_bonuses : result of collect_upset_bonuses(), or None

    Returns a log list so the between_seasons state can display changes.
    """
    upset_bonuses   = upset_bonuses or {}
    position_map    = {row["team"]: i + 1 for i, row in enumerate(standings)}
    total_teams     = len(standings)
    log             = []
    
    for team in teams:
        old = round(team.prestige, 1)
        
        # Stage 1: Decay
        team.prestige *= (1.0 - TEAM_DECAY_RATE)
        
        # Stage 2: Position Award
        pos = position_map.get(team.name)
        if pos is not None:
            team.prestige += _position_award(pos, total_teams, comp_prestige)
            
        # Stage 3: Upset Bonus
        team.prestige += upset_bonuses.get(team.name, 0.0)
        
        # Stage 4: Floor
        team.prestige = max(team.prestige, TEAM_PRESTIGE_FLOOR)
        team.prestige = round(team.prestige, 1)
        
        log.append({
            "team":         team.name,
            "old_prestige": old,
            "new_prestige": team.prestige,
            "delta":        round(team.prestige - old, 1),
            "position":     pos,
        })
        
    return log


# Nation prestige update

def update_nation_prestige(
    nations: dict,
    teams,
    standings: list[dict],
    comp_prestige: float,
    tier_seasons: dict,
    committed_tiers: dict,
) -> list[dict]:
    """
    Update prestige for each nation whose clubs competed this season.

    The nation prestige formula:
        new = old * (1 - decay) + avg_club_award * league_weight

    avg_club_award is the mean position award across all of the nation's clubs.
    league_weight is prestige_weight_league from nations.yaml (e.g. 0.60).

    TIER CHANGE GUARD
    After updating, derive the new tier from prestige. If it differs from
    the last committed tier, start (or continue) counting consecutive seasons
    at the new level. Once the count reaches tier_change_min_seasons, commit
    the new tier and reset the counter. Until then, the old tier stays active.

    Both dicts are owned by the engine and persisted to world_state.json.
    """
    log = []
    
    # Group runtime Team objects by nation_id for easy access
    nation_teams: dict[str, list] = {}
    for team in teams:
        nid = getattr(team, "nation_id", None)
        if nid:
            nation_teams.setdefault(nid, []).append(team)
            
    position_map = {row["team"]: i + 1 for i, row in enumerate(standings)}
    total_teams = len(standings)
    
    for nation_id, nation in nations.items():
        club_list = nation_teams.get(nation_id, [])
        if not club_list:
            continue  # No clubs from this nation competed, skip prestige update
        
        old_prestige = round(nation.prestige, 1)
        last_committed_tier = committed_tiers.get(nation_id, prestige_to_tier(old_prestige))
        
        # Stage 1: Decay
        nation.prestige *= (1.0 - nation.prestige_decay)
        
        # Stage 2: League Contribution
        awards = [
            _position_award(position_map[t.name], total_teams, comp_prestige)
            for t in club_list if t.name in position_map
        ]
        if awards:
            avg_award = sum(awards) / len(awards)
            nation.prestige += avg_award * nation.prestige_weight_league
            
        # Stage 3: Floor
        nation.prestige = max(nation.prestige, nation.prestige_floor)
        nation.prestige = round(nation.prestige, 1)
        
        # Tier Change Guard
        derived_tier = prestige_to_tier(nation.prestige)
        
        if derived_tier == last_committed_tier:
            # Same tier, reset counter
            tier_seasons[nation_id] = 0
        else:
            # Prestige has crossed a threshold - count consecutive seasons
            tier_seasons[nation_id] = tier_seasons.get(nation_id, 0) + 1
            
        tier_changed =  False
        if tier_seasons.get(nation_id, 0) >= nation.tier_change_min_seasons:
            committed_tiers[nation_id]  = derived_tier
            tier_seasons[nation_id]     = 0
            tier_changed                = True
            
        effective_tier = committed_tiers.get(nation_id, last_committed_tier)
        
        log.append({
            "nation": nation.name,
            "old_prestige": old_prestige,
            "new_prestige": nation.prestige,
            "delta": round(nation.prestige - old_prestige, 1),
            "derived_tier": derived_tier,
            "effective_tier": effective_tier,
            "tier_changed": tier_changed,
            "guard_count": tier_seasons.get(nation_id, 0),
        })
        
    return log