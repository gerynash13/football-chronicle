from __future__ import annotations

from dataclasses import dataclass, field
from data_loader import Journalist
from rng import rng
from player_refs import new_id

SCOPE_ORDER = ["local", "regional", "national", "continental", "global"]

def _scope_rank(scope: str) -> int:
    return SCOPE_ORDER.index(scope)

class ArticleStore:
    """
    Published articles — one journalist's told version of an event.
    Unlike NewsFeed (a bounded, "what's happening lately" log), this is
    meant to hold a player's or club's full media history across however
    long the save has been running — the player media tab is meant to
    show everything ever written about them, not just the last 2000
    items. No cap for now. If that becomes a genuine memory problem on
    a very long playthrough, the right fix is persisting this to its
    own save file the way records_data.json already persists RecordBook
    — not silently dropping old articles.
    """
    def __init__(self):
        self._articles: list[Article] = []
        
    def publish(self, article: Article) -> None:
        self._articles.append(article)
        
    def get_articles(
        self,
        *,
        team: str | None = None,
        player_id: str | None = None,
        journalist_id: str | None = None,
        tier: str | None = None,
        limit: int | None = None,
    ) -> list[Article]:
        results = []
        for art in self._articles:
            if team and team not in art.teams:
                continue
            if player_id and player_id not in art.players:
                continue
            if journalist_id and journalist_id != art.journalist_id:
                continue
            if tier and art.tier != tier:
                continue
            results.append(art)
        if limit:
            results = results[-limit:]
        return results
    
    def get_recent(self, n: int=20) -> list[Article]:
        return self._articles[-n:]
    
    def __len__(self) -> int:
        return len(self._articles)

@dataclass
class Article:
    journalist_id: str
    journalist_name: str
    headline: str
    body: str
    date: str
    season: str
    event_type: str
    tier: str
    id: str = field(default_factory=lambda: new_id()[:8])
    teams: list = field(default_factory=list)
    players: list = field(default_factory=list)
    
COMPREHENSIVE_TIERS = {"local", "regional", "national"}

EVENT_MAGNITUDE = {
    "match_result":         "national",
    "hat_trick":            "national",
    "goal_milestone":       "national",
    "injury_update":        "local",
    "promotion":            "national",
    "relegation":           "national",
    "manager_sacked":       "national",
    "transfer_completed":   "national",
    "wonderkid_emerges":    "national",
    "competition_winner":   "continental",
    "record_broken":        "global",
}

def _event_magnitude(event: dict) -> str:
    """How big a story this inherently is, independent of whose patch it's in."""
    return EVENT_MAGNITUDE.get(event["type"], "local")

def _involves_team(event: dict, team_name: str) -> bool:
    return team_name in (
        event.get("home_team"), event.get("away_team"),
        event.get("team"), event.get("winner")
    )
    
def _team_nation(teams: list, team_name: str | None) -> str | None:
    if not team_name:
        return None
    team = next((t for t in teams if t.name == team_name), None)
    return team.nation_id if team else None

def _in_jurisdiction(journalist: Journalist, event: dict, teams: list) -> bool:
    """Whether this event falls inside the patch this journalist comprehensively covers."""
    if journalist.favorite_team and _involves_team(event, journalist.favorite_team):
        return True
    if journalist.tier == "national" and journalist.nation_id:
        for key in ("home_team", "away_team", "team", "winner"):
            if _team_nation(teams, event.get(key)) == journalist.nation_id:
                return True
    return False

def covers_event(journalist: Journalist, event: dict, teams: list) -> bool:
    """
    Narrow-patch tiers (local/regional/national) cover their own patch
    unconditionally, regardless of how routine the story is — that's
    their whole beat. Everyone else only crosses in (or covers their
    own nominal "patch", for continental/global, which is too broad to
    be comprehensive about) if the story is big enough to matter
    worldwide.
    """
    if journalist.tier in COMPREHENSIVE_TIERS and _in_jurisdiction(journalist, event, teams):
        return True
    return _event_magnitude(event) == "global"

MATCH_REPORT_TEMPLATES = {
    "analytical": {
        "win": [
            "{winner} {verb} {loser} {score} in matchday {matchday} of {competition}.",
        ],
        "draw": [
            "{home_team} and {away_team} shared the points in a tightly contested {score} draw.",
        ],
        "favorite_win": [
            "{winner} {verb} {loser} {score}, a result that will please everyone connected with the club.",
        ],
        "favorite_loss": [
            "A {score} defeat to {winner} that {loser} will want to put behind them quickly, though the performance had encouraging spells.",
        ],
    },
    "dramatic": {
        "win": [
            "{winner} {verb} {loser} in a result that will turn heads: {score}.",
        ],
        "draw": [
            "A breathless {score} draw between {home_team} and {away_team} left both sets of fans drained.",
        ],
        "favorite_win": [
            "{winner} produce a statement display, {verb} {loser} {score} in front of a jubilant crowd!",
        ],
        "favorite_loss": [
            "Heartbreak for {loser}, undone {score} by {winner} in a result that will sting for days.",
        ],
    },
    "gossip": {
        "win": [
            "Whispers already circulating after {loser}'s defeat to {winner} in a match that finished {score} — how long before changes are made?",
        ],
        "draw": [
            "A flat draw between {home_team} and {away_team} has tongues wagging about what's really going on behind the scenes: {score}.",
        ],
        "favorite_win": [
            "{winner} silence the doubters with a {score} win over {loser} — sources close to the squad say morale has never been higher.",
        ],
        "favorite_loss": [
            "Questions being asked after {loser}'s {score} loss to {winner} — insiders whisper this isn't the first dressing-room wobble this month.",
        ],
    },
    "opinionated": {
        "win": [
            "{winner}'s win over {loser}, in a match that finished {score}, says everything about where these two clubs are headed this season.",
        ],
        "draw": [
            "A {score} draw that will satisfy absolutely nobody at {home_team} or {away_team}.",
        ],
        "favorite_win": [
            "Make no mistake — {winner}'s {score} win over {loser} is exactly the statement this club needed to make.",
        ],
        "favorite_loss": [
            "{loser} deserved far better than this {score} defeat to {winner} — the officials, not the players, should be answering questions.",
        ],
    },
    "investigative": {
        "win": [
            "Beneath the {score}, {loser}'s defeat to {winner} raises real questions about squad depth heading into the run-in.",
        ],
        "draw": [
            "A {score} draw that neither side will be happy with — and the underlying pattern of results suggests why.",
        ],
        "favorite_win": [
            "A {score} win over {loser} that flatters {winner} slightly less than the scoreline suggests — but a win is a win.",
        ],
        "favorite_loss": [
            "A {score} loss to {winner} that fits an uncomfortable pattern for {loser} worth watching over the coming weeks.",
        ],
    },
}

def write_article(journalist: Journalist, event: dict, season: str) -> Article:
    """
    Produce one journalist's telling of an event they've already been
    confirmed to cover. Returns None for event types we don't have a
    report template for yet.
    """
    if event["type"] == "match_result":
        return _write_match_report(journalist, event, season)
    return None

def _scorer_sentence(scorers: list[dict], team: str) -> str:
    """A standalone trailing sentence naming this team's scorers, or '' if none known."""
    names = [s["player"] for s in scorers if s["team"] == team and s.get("player")]
    if not names:
        return ""
    counts = {}
    ordered = []
    for n in names:
        if n not in counts:
            ordered.append(n)
        counts[n] = counts.get(n, 0) + 1
    parts = [f"{n} ({counts[n]})" if counts[n] > 1 else n for n in ordered]
    who = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    verb = "scored" if len(parts) == 1 else "were on target"
    return f"{who} {verb} for {team}."

WIN_VERBS = {
    "measured": ["controlled", "saw out", "managed", "handled", "navigated", "saw off", "beat", "defeated"],
    "exaggerated": ["brushed aside", "tore through", "smashed", "obliterated", "crushed", "demolished", "routed", "trounced"],
}

def _win_verb(reliability: float) -> str:
    """Pick a verb for a winning team, based on how reliable the journalist is. Low reliability = more exaggerated verbs."""
    pool = WIN_VERBS["exaggerated"] if reliability < 0.5 else WIN_VERBS["measured"]
    return rng.choice(pool)

def _select_outcome(journalist: Journalist, winner, loser, outcome: str) -> str:
    """
    Draws stay neutral regardless of bias for now — not modeling a
    "point gained vs. two points dropped" distinction yet, deliberately,
    same call as every other corner we've cut to date: easy to add a
    favorite_draw bucket later, not worth it before we've seen the win/
    loss version in action.
    """
    if outcome == "draw":
        return "draw"
    if journalist.favorite_team == winner:
        return "favorite_win"
    if journalist.favorite_team == loser:
        return "favorite_loss"
    return "win"

def _write_match_report(journalist: Journalist, event: dict, season: str) -> Article:
    home, away = event["home_team"], event["away_team"]
    hg, ag = event["home_goals"], event["away_goals"]
    scorers = event.get("scorers", [])
    
    if hg > ag:
        winner, loser, outcome = home, away, "win"
        winner_score = f"{hg}-{ag}"
        loser_score = f"{ag}-{hg}"
    elif ag > hg:
        winner, loser, outcome = away, home, "win"
        winner_score = f"{ag}-{hg}"
        loser_score = f"{hg}-{ag}"
    else:
        winner, loser, outcome = None, None, "draw"
        winner_score = loser_score = f"{hg}-{ag}"
        
    bucket = _select_outcome(journalist, winner, loser, outcome)
    verb = _win_verb(journalist.reliability) if bucket in ("win", "favorite_win") else ""
    score = loser_score if bucket == "favorite_loss" else winner_score
    
    pool = MATCH_REPORT_TEMPLATES.get(journalist.style, MATCH_REPORT_TEMPLATES["analytical"])[bucket]
    body = rng.choice(pool).format(
        winner=winner, loser=loser, home_team=home, away_team=away, 
        score=score, competition=event.get("competition", "the league"),
        matchday=event.get("matchday"), verb=verb
    )
    
    scorer_sentences = [
        sentence
        for sentence in (_scorer_sentence(scorers, home), _scorer_sentence(scorers, away))
        if sentence
    ]
    if scorer_sentences:
        body += " " + " ".join(scorer_sentences)
    
    headline = (
        f"{winner} {winner_score} {loser}"
        if winner else f"{home} {winner_score} {away}"
    )
    
    return Article(
        journalist_id=journalist.id,
        journalist_name=journalist.name,
        headline=headline,
        body=body,
        date=event["date"],
        season=season,
        event_type=event["type"],
        tier=journalist.tier,
        teams=[home, away],
        players=list(dict.fromkeys(s["player_id"] for s in scorers if s.get("player_id"))),
    )