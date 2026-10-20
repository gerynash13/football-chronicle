"""
api.py — Flask API
 
Thin HTTP layer over GameEngine. No game logic lives here.
Every endpoint either calls engine.advance(), engine.choose(), or reads
engine state that already exists — nothing else.
 
RUNNING
=======
    python api.py
 
Starts on http://localhost:5000 by default.
Pass --port <n> to use a different port.
 
ENDPOINTS
=========
POST /api/advance
    Move the game forward one step.
    Body (optional): {"load_save": true}  — resume from save file on first call
    Returns: state dict (see engine.py for full schema per type)
 
POST /api/choose
    Resolve the current blocking event.
    Body: {"index": 0}  — 0-based index of the chosen option
    Returns: state dict
 
GET /api/state
    Return the last state without advancing.
    Safe to call repeatedly — no side effects.
    Returns: state dict, or {"type": "not_started"} if advance hasn't been called
 
GET /api/news
    Return news feed events.
    Query params:
        relevance   — "global" | "regional" | "local"
        type        — event type filter (e.g. "hat_trick")
        team        — team name filter
        limit       — max events to return (default 20)
    Returns: list of event dicts
 
GET /api/inbox
    Return calendar inbox items (notifications the player hasn't seen yet).
    Returns: list of {title, description, date, category, is_read}
 
GET /api/teams
    Return all teams with current season stats.
    Returns: list of team summary dicts
 
GET /api/player/<player_id>
    Return full player details.
    Returns: player dict or 404
"""

import sys
import json
import datetime
import dataclasses
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from flask.json.provider import DefaultJSONProvider

import threading
_lock = threading.Lock()

from classes import GameEngine

class CustomJSONProvider(DefaultJSONProvider):
    @staticmethod
    def default(obj):
        if isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)

# App setup
app = Flask(__name__, static_folder="frontend", static_url_path="")
app.json = CustomJSONProvider(app)
CORS(app) # Allow all origins for local development

# Single engine instance for the lifetime of the server process
# On restart it will be reloaded from the save file.
engine = GameEngine(start_year=1896, num_seasons=50)

# Cache the last state so GET /api/state is always available without advancing
_last_state: dict | None = None

@app.route("/")
def index():
    return app.send_static_file("index.html")

# Core game loop endpoints

@app.route("/api/advance", methods=["POST"])
def advance():
    """
    The main driver. We call this repeatedly to advance the game forward.
    """
    global _last_state
    with _lock:
        body        = request.get_json(silent=True) or {}
        load_save   = bool(body.get("load_save", False))
        state       = engine.advance(load_save=load_save)
        _last_state = state
    
    return jsonify(state)

@app.route("/api/choose", methods=["POST"])
def choose():
    """
    Resolve the current blocking event by selecting an option.
    Passing an invalid index returns a 400 error.
    """
    global _last_state
    with _lock:
        body  = request.get_json(silent=True) or {}
        index = body.get("index")
    
    if index is None:
        return jsonify({"error": "Request body missing 'index' field."}), 400
    
    state = engine.choose(int(index))
    
    if state.get("type") == "error":
        return jsonify(state), 400
    
    _last_state = state
    return jsonify(state)


# Read-only state endpoints

@app.route("/api/state", methods=["GET"])
def get_state():
    """
    Return the last state produced by advance() or choose() without moving the game forward.
    Safe to poll from the frontend.
    """
    if _last_state is None:
        return jsonify({
            "type": "not_started",
            "message": "Call POST /api/advance to advance the game.",
            "managed_team": engine.managed_team,
        })
    return jsonify({**_last_state, "managed_team": engine.managed_team})

@app.route("/api/news", methods=["GET"])
def get_news():
    """
    Return news feed events with optional filtering.
    
    Query parameters:
        relevance   — "global" | "regional" | "local"
        type        — event type string (e.g. "hat_trick", "match_result")
        team        — team name (matches home_team, away_team or team fields)
        limit       — integer, max events to return (default 20, max 100)
    """
    relevance   = request.args.get("relevance")
    event_type  = request.args.get("type")
    team        = request.args.get("team")
    limit       = min(int(request.args.get("limit", 20)), 100)
    
    events = engine.news_feed.get_events(
        relevance=relevance,
        event_type=event_type,
        team=team,
        limit=limit,
    )
    return jsonify(events)

@app.route("/api/articles", methods=["GET"])
def get_articles():
    """
    Return generated news articles with optional filtering.

    Query parameters:
        team          — team name (matches either side of the story)
        player_id     — player ID
        journalist_id — filter to one journalist's byline
        tier          — "local" | "regional" | "national" | "continental" | "global"
        limit         — integer, max articles to return (default 20, max 100)
    """
    team          = request.args.get("team")
    player_id     = request.args.get("player_id")
    journalist_id = request.args.get("journalist_id")
    tier          = request.args.get("tier")
    limit         = min(int(request.args.get("limit", 20)), 100)
    
    articles = engine.newsroom.get_articles(
        team=team,
        player_id=player_id,
        journalist_id=journalist_id,
        tier=tier,
        limit=limit,
    )
    return jsonify([dataclasses.asdict(a) for a in articles])

@app.route("/api/inbox", methods=["GET"])
def get_inbox():
    """
    Return calendar inbox items, background notifications that haven't been acknowledged
    by the player yet.
    """
    if not engine.calendar:
        return jsonify([])
    
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    items = []
    for event in engine.calendar.inbox:
        if unread_only and event.is_read:
            continue
        items.append({
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "date": event.date.isoformat(),
            "category": event.category,
            "is_read": event.is_read,
        })
    return jsonify(items)

@app.route("/api/teams", methods=["GET"])
def get_teams():
    """
    Return all teams with their current squad size and season stats from the live standings.
    Useful for building league table views.
    """
    if not engine.teams:
        return jsonify([])
    
    standings = {
        row["team"]: row
        for row in engine._serialise_standings()
    } if engine.comp else {}
    
    teams = []
    for team in engine.teams:
        row = standings.get(team.name, {})
        teams.append({
            "name": team.name,
            "prestige": team.prestige,
            "home_region": team.home_region,
            "morale": team.morale,
            "budget": team.budget,
            "wage_budget": team.wage_budget,
            "squad_size": len(team.squad),
            "board_confidence": team.board_confidence,
            "fan_satisfaction": team.fan_satisfaction,
            # Standing columns (empty dict if competition not yet started)
            "played": row.get("played", 0),
            "wins": row.get("wins", 0),
            "draws": row.get("draws", 0),
            "losses": row.get("losses", 0),
            "goals_for": row.get("goals_for", 0),
            "goals_against": row.get("goals_against", 0),
            "goal_difference": row.get("goal_difference", 0),
            "points": row.get("points", 0),
        })
        
    # Sort by points descending to match league table order
    teams.sort(key=lambda t: (-t["points"], -t["goal_difference"], -t["wins"], -t["goals_for"]))
    return jsonify(teams)

@app.route("/api/player/<player_id>", methods=["GET"])
def get_player(player_id: str):
    """
    Return full player details by their ID.
    Returns: player dict or 404 if not found
    """
    for team in engine.teams:
        for player in team.squad + team.retired + team.youth + team.released:
            if player.id == player_id:
                return jsonify(_serialize_player(player, team.name, _sim_today()))
            
    abort(404)
    
@app.route("/api/squad/<team_name>", methods=["GET"])
def get_squad(team_name: str):
    """
    Return full squad details by team name.
    Returns: squad dict or 404 if not found
    """
    team = next((t for t in engine.teams if t.name == team_name), None)
    if team is None:
        abort(404)
    reference_date = _sim_today()
    return jsonify([
        _serialize_player(player, team.name, reference_date)
        for player in team.squad
    ])
    
@app.route("/api/youth/<team_name>", methods=["GET"])
def get_youth(team_name: str):
    team = next((t for t in engine.teams if t.name == team_name), None)
    if team is None:
        abort(404)
    ref = _sim_today()
    return jsonify([_serialize_player(p, team.name, ref) for p in team.youth])


# Serialization helpers

def _sim_today() -> datetime.date | None:
    """The game's current date, or None before the game has started."""
    return engine.calendar.current_date if engine.calendar else None

def _serialize_player(
    player, team_name: str, reference_date: datetime.date | None
) -> dict:
    """
    Convert a player object to a JSON-friendly dict.
    Called by get_player() and get_squad().
    """
    return{
        "id":                       player.id,
        "name":                     player.name,
        "position":                 player.position,
        "role":                     player.role,
        "birth_date":               player.birth_date.isoformat(),
        "age":                      player.age_on(reference_date) if reference_date else None,
        "nationality":              player.nationality,
        "birth_region":             player.birth_region,
        "preferred_foot":           player.preferred_foot,
        "current_ability":          player.current_ability,
        "potential_ability":        player.potential_ability,
        "is_wonderkid":             player.is_wonderkid,
        "team":                     team_name,
        "morale":                   player.morale,
        "manager_relationship":     player.manager_relationship,
        "contract_expires":         player.contract_expires,
        "wage":                     player.wage,
        "is_injured":               player.is_injured,
        "injury_severity":          player.injury_severity,
        "injury_until":             player.injury_until.isoformat() if player.injury_until else None,
        "is_suspended":             player.is_suspended,
        "suspension_matches_left":  player.suspension_matches_left,
        "is_retired":               player.is_retired,
        # Season stats:
        "goals":                    player.goals,
        "assists":                  player.assists,
        "appearances":              player.appearances,
        "clean_sheets":             player.clean_sheets,
        "season_avg_rating":        player.season_avg_rating,
        "yellow_cards":             player.yellow_cards,
        "red_cards":                player.red_cards,
        # Career stats
        "career_goals":             player.career_goals,
        "career_assists":           player.career_assists,
        "career_appearances":       player.career_appearances,
        "career_trophies":          player.career_trophies,
        "career_history":           player.career_history,
    }
    
    
# Dev utilities

@app.route("/api/cup_bracket", methods=["GET"])
def get_cup_bracket():
    return jsonify(engine.get_cup_bracket())

@app.route("/api/ping", methods=["GET"])
def ping():
    """
    Health check, returns OK and current engine season.
    """
    return jsonify({
        "status": "ok",
        "season": engine.season_year or "not started",
        "teams": len(engine.teams),
        "managed_team": engine.managed_team
    })
    
    
# Entry point

if __name__ == "__main__":
    port = 5000
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
        
    print(f"\n  Football Sim")
    print(f"  Running on http://localhost:{port}")
    print(f"  Press Ctrl+C to exit\n")
    
    app.run(debug=True, port=port, use_reloader=False)
    # use_reloader prevents the engine from being initialized twice on startup.