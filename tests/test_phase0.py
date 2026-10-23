import datetime
import pytest
from classes.team import Team
from classes.player import Player
from classes.engine import GameEngine
from player_refs import find_player
from save_slot import SaveSlot
from validate_data import validate
from rng import rng
from lifecycle import youth_intake

def make_engine(tmp_path, start_year=1896, seasons=1, seed=123):
    return GameEngine(start_year=start_year, num_seasons=seasons, seed=seed,
                      slot=SaveSlot("test", root=tmp_path))


def play(engine, until=("game_over",), load_save=False):
    """Yield every state; always picks option 0 for choices."""
    state = engine.advance(load_save=load_save)
    while True:
        yield state
        if state["type"] in until or state["type"] == "error":
            return
        state = engine.choose(0) if state["type"] == "blocking_event" else engine.advance()


def test_same_seed_gives_same_world(tmp_path):
    def summary(engine):
        return [(s["season"], s["champion"],
                 [(r["team"], r["points"]) for r in s["final_standings"]])
                for s in play(engine) if s["type"] == "season_end"]
    a = summary(make_engine(tmp_path / "a", seasons=2))
    b = summary(make_engine(tmp_path / "b", seasons=2))
    assert len(a) == 2
    assert a == b    # if this fails, some file still uses the global `random`


import datetime
from match_model import INJURY_DAYS_PER_MATCH


def test_bans_and_injuries_are_actually_served(tmp_path, monkeypatch):
    monkeypatch.setattr("classes.engine.get_yellow_threshold", lambda season: 2)
    engine = make_engine(tmp_path, start_year=1970)
    banned = {}    # player_id -> [team, matches still to miss]
    hurt = {}      # player_id -> last day he must sit out
    served = registered = 0

    for state in play(engine, until=("season_end",)):
        if state["type"] != "matchday":
            continue
        today = datetime.date.fromisoformat(state["date"])
        for r in state["results"]:
            for team, xi_key in ((r["home_team"], "home_xi"), (r["away_team"], "away_xi")):
                in_xi = {p["id"] for p in r[xi_key]}
                for pid, entry in list(banned.items()):
                    if entry[0] == team:
                        assert pid not in in_xi, f"{pid} played while banned"
                        entry[1] -= 1
                        served += 1
                        if entry[1] == 0:
                            del banned[pid]
                for pid, until in list(hurt.items()):
                    if pid in in_xi:
                        assert today > until, f"{pid} played while injured"
        # register new absences AFTER checking today's matches
        for r in state["results"]:
            for evt in r["events"]:
                if evt["type"] == "injury":
                    hurt[evt["player_id"]] = today + datetime.timedelta(
                        days=INJURY_DAYS_PER_MATCH * evt["matches_out"])
                    registered += 1
                elif evt["type"] == "red_card":
                    banned[evt["player_id"]] = [evt["team"],
                                                1 if evt.get("reason") == "second_yellow" else 3]
        for s in state["newly_suspended"]:
            p, _ = find_player(engine.teams, name=s["player"], team_name=s["team"])
            if p:
                banned[p.id] = [s["team"], 1]
        for i in state["new_injuries"]:
            p, _ = find_player(engine.teams, name=i["player"], team_name=i["team"])
            if p:
                hurt[p.id] = today + datetime.timedelta(days=INJURY_DAYS_PER_MATCH * i["matches"])
                registered += 1
    assert served > 0 and registered > 0


def test_resume_continues_from_saved_season(tmp_path):
    a = make_engine(tmp_path, seasons=3)
    list(play(a, until=("between_seasons",)))
    b = make_engine(tmp_path, seasons=3)
    b.advance(load_save=True)
    assert b.season_year == a.season_year == "1897/98"
    assert b.managed_team == a.managed_team
    assert [t.prestige for t in b.teams] == [t.prestige for t in a.teams]
    
def test_data_files_are_consistent():
    assert validate() == []


def test_retired_player_is_not_selected():
    team = Team("T", 60, 60, 60)
    for pos, n in (("GK", 1), ("DEF", 3), ("MID", 4), ("FWD", 6)):
        for i in range(n):
            team.add_player(Player(f"{pos}{i}", pos, datetime.date(1870, 1, 1), 60, 60))
    star = team.squad[-1]
    star.current_ability = 99
    star.is_retired = True
    assert star not in team.select_starting_xi()
    
def test_mid_season_save_resumes_exactly(tmp_path):
    a = make_engine(tmp_path, seasons=3)
    seen_boundary, matchdays_after = False, 0
    last = None
    for s in play(a):
        last = s
        if s["type"] == "between_seasons":
            seen_boundary = True
        elif seen_boundary and s["type"] == "matchday":
            matchdays_after += 1
            if matchdays_after == 3:
                break                     # "quit" three matchdays into season 2

    b = make_engine(tmp_path, seasons=3)
    resumed = b.advance(load_save=True)

    assert resumed == last
    stats = lambda e: [(p.id, p.goals, p.appearances) for t in e.teams for p in t.squad]
    assert stats(a) == stats(b)
    rng_state = rng.getstate()
    next_a = a.advance()
    
    rng.setstate(rng_state)
    next_b = b.advance()
    
    assert next_a == next_b
    
def test_better_youth_facilities_produce_better_prospects():
    cfg = {"pa_cap": 200, "wonderkid_pa_cap": 200, "wonderkid_chance": 0.0}

    def mean_pa(youth_facility):
        team = Team("T", 60, 60, 60)
        team.facilities["youth"] = youth_facility
        pas = []
        for _ in range(60):
            team.squad = []
            pas += [p.potential_ability for p in youth_intake(team, cfg, 60.0, "1897/98")]
        return sum(pas) / len(pas)

    assert mean_pa(90) > mean_pa(10) + 8