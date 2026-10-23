import json
import sqlite3
from contextlib import closing

SCHEMA = """
CREATE TABLE IF NOT EXISTS standings (
    season TEXT, competition TEXT, position INTEGER, team_id TEXT, team TEXT,
    played INTEGER, wins INTEGER, draws INTEGER, losses INTEGER,
    goals_for INTEGER, goals_against INTEGER, goal_difference INTEGER, points INTEGER,
    PRIMARY KEY (season, competition, team_id)
);
CREATE TABLE IF NOT EXISTS trophies (
    season TEXT, competition TEXT,
    winner_id TEXT, winner TEXT, runner_up_id TEXT, runner_up TEXT,
    PRIMARY KEY (season, competition)
);
CREATE TABLE IF NOT EXISTS matches (
    season TEXT, competition TEXT, matchday INTEGER, round INTEGER, date TEXT,
    home_id TEXT, home TEXT, away_id TEXT, away TEXT,
    home_goals INTEGER, away_goals INTEGER, decided_in TEXT, goals TEXT
);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches (season, competition);
CREATE TABLE IF NOT EXISTS player_seasons (
    player_id TEXT, season TEXT, team_id TEXT, team TEXT, player TEXT,
    position TEXT, age INTEGER, appearances INTEGER, goals INTEGER, assists INTEGER,
    clean_sheets INTEGER, yellow_cards INTEGER, red_cards INTEGER,
    avg_rating REAL, ca INTEGER,
    PRIMARY KEY (player_id, season, team_id)
);
CREATE TABLE IF NOT EXISTS leaderboards (
    season TEXT, category TEXT, rank INTEGER, player_id TEXT, player TEXT,
    team_id TEXT, team TEXT, value INTEGER,
    PRIMARY KEY (season, category, rank)
);
"""

COLUMNS = {
    "standings": ["season", "competition", "position", "team_id", "team", "played", "wins",
                  "draws", "losses", "goals_for", "goals_against", "goal_difference", "points"],
    "trophies": ["season", "competition", "winner_id", "winner", "runner_up_id", "runner_up"],
    "matches": ["season", "competition", "matchday", "round", "date", "home_id", "home",
                "away_id", "away", "home_goals", "away_goals", "decided_in", "goals"],
    "player_seasons": ["player_id", "season", "team_id", "team", "player", "position", "age",
                       "appearances", "goals", "assists", "clean_sheets", "yellow_cards",
                       "red_cards", "avg_rating", "ca"],
    "leaderboards": ["season", "category", "rank", "player_id", "player", "team_id", "team", "value"],
}

def _insert_sql(table):
    cols = COLUMNS[table]
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)})"

class Archive:
    def __init__(self, path):
        self.path = path
        
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _query(self, sql, params=()):
        with closing(self._connect()) as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]
        
    def init(self):
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            
    def write_season(self, payload):
        """Replace everything stored for this season, all or nothing"""
        season = payload["season"]
        with closing(self._connect()) as conn, conn:
            for table in COLUMNS:
                conn.execute(f"DELETE FROM {table} WHERE SEASON = ?", (season,))
                conn.executemany(_insert_sql(table), payload[table])
                
    # ── questions the history pages will ask ─────────────────────────────────
    def champions(self, competition=None):
        if competition:
            return self._query("SELECT * FROM trophies WHERE competition = ? ORDER BY season",
                               (competition,))
        return self._query("SELECT * FROM trophies ORDER BY season, competition")
    
    def table(self, season, competition):
        return self._query("SELECT * FROM standings WHERE season = ? AND competition = ? "
                           "ORDER BY position", (season, competition))
    
    def season_matches(self, season, competition):
        return self._query("SELECT * FROM matches WHERE season = ? AND competition = ? "
                           "ORDER BY date, matchday", (season, competition))
        
    def team_history(self, team_id):
        return self._query("""
            SELECT s.season, s.competition, s.position, s.points, s.wins, s.draws, s.losses,
                s.goals_for, s.goals_against,
                (SELECT GROUP_CONCAT(t.competition) FROM trophies t
                WHERE t.season = s.season AND t.winner_id = s.team_id) AS trophies
            FROM standings s WHERE s.team_id = ? ORDER BY season""", (team_id,))
        
    def leaders(self, category="goals", limit=10, team_id=None):
        """All-time totals. With team_id: that club's all-time leaders (club legends)."""
        column = {"goals": "goals", "assists": "assists", "appearances": "appearances",
                  "clean_sheets": "clean_sheets"}[category]
        where, params = ("WHERE team_id = ?", (team_id,)) if team_id else ("", ())
        return self._query(f"""
            SELECT player_id, MAX(player) AS player, SUM({column}) AS total,
                COUNT(DISTINCT season) AS seasons
            FROM player_seasons {where}
            GROUP BY player_id ORDER BY total DESC LIMIT ?""", params + (limit,))

# ── building the payload from the live game objects ──────────────────────────

def _table(comp):
    return sorted(comp.standings.items(),
                  key=lambda x: (-x[1]["points"], -x[1]["goal_difference"], -x[1]["goals_for"], x[0]))
    
def leaderboard_rows(season, teams, categories):
    """categories: {"goals": [players, best first], ...}"""
    owner = {p.id: t for t in teams for p in t.squad}
    values = {
        "goals":            lambda p: p.goals,
        "assists":          lambda p: p.assists,
        "clean_sheets":     lambda p: p.clean_sheets,
        "avg_rating":       lambda p: round(p.season_avg_rating, 2),
    }
    rows = []
    for category, players in categories.items():
        rank = 0
        for p in players:
            value = values[category](p)
            if category != "avg_rating" and value == 0:
                break
            rank += 1
            team = owner[p.id]
            rows.append({"season": season, "category": category, "rank": rank,
                         "player_id": p.id, "player": p.name, 
                         "team_id": team.id, "team": team.name, "value": value})
    return rows

def build_payload(season, season_end, teams, competitions, trophies, leaderboards):
    ids = {t.name: t.id for t in teams}
    standings, matches, player_seasons = [], [], []
    
    for comp in competitions:
        key = comp.key or comp.name
        if comp.type == "league":
            for pos, (name, s) in enumerate(_table(comp), 1):
                standings.append({"season": season, "competition": key, "position": pos,
                                  "team_id": ids[name], "team": name, **s})
        for r in comp.results:
            goals = [{"player_id": e.get("player_id"), "player": e.get("player"),
                      "team": e["team"], "minute": e["minute"]}
                     for e in r.get("events", []) if e["type"] == "goal"]
            matches.append({"season": season, "competition": key, 
                            "matchday": r.get("matchday"), "round": r.get("round"),
                            "date": r.get("date"),
                            "home_id": r["home_team_id"], "home": r["home_team"],
                            "away_id": r["away_team_id"], "away": r["away_team"],
                            "home_goals": r["home_goals"], "away_goals": r["away_goals"],
                            "decided_in": r.get("decided_in"), "goals": json.dumps(goals)})
    for team in teams:
        for p in team.squad:
            if p.appearances == 0:
                continue
            player_seasons.append({
                "player_id": p.id, "season": season, "team_id": team.id, "team": team.name,
                "player": p.name, "position": p.position, "age": p.age_on(season_end),
                "appearances": p.appearances, "goals": p.goals, "assists": p.assists,
                "clean_sheets": p.clean_sheets, "yellow_cards": p.yellow_cards,
                "red_cards": p.red_cards,
                "avg_rating": round(p.season_avg_rating, 2) if p.season_rating_appearances else None,
                "ca": p.current_ability
            })
            
    return {"season": season, "standings": standings, "trophies": trophies, "matches": matches,
            "player_seasons": player_seasons, "leaderboards": leaderboards}