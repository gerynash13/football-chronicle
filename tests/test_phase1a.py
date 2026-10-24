import datetime
from strength import line_ratings
from simulation import simulate_match
from lifecycle import retire_players, youth_intake, TARGET_SQUAD, ai_promotions, release_overage, promote, demote
from data_manager import save_teams_to_file, load_teams_from_file
from classes.team import Team
from classes.player import Player
from test_phase0 import make_engine, play
from archive import Archive, build_payload

def _squad(n_gk=1):
    team = Team("T", 60, 60, 60)
    for pos, n in (("GK", n_gk), ("DEF", 3), ("MID", 4), ("FWD", 6)):
        for i in range(n):
            team.add_player(Player(f"{pos}{i}", pos, datetime.date(1870, 1, 1), 60, 60))
    return team

def test_xi_is_eleven_even_without_a_goalkeeper():
    team = _squad()
    team.squad[0].is_injured = True
    xi = team.select_starting_xi()
    assert len(xi) == 11
    assert any(p.playing_as == "GK" for p in xi)
    
def test_better_players_raise_the_matching_line():
    xi = _squad().select_starting_xi()
    before = line_ratings(xi)
    for p in xi:
        if p.position == "FWD":
            p.attributes = {k: v + 10 for k, v in p.attributes.items()}
    after = line_ratings(xi)
    assert after["attack"] > before["attack"]
    assert after["defense"] == before["defense"]
    
def test_a_missing_player_weakens_the_team():
    xi = _squad().select_starting_xi()
    full = line_ratings(xi)["attack"]
    one_fwd = next(p for p in xi if p.position == "FWD")
    assert line_ratings([p for p in xi if p is not one_fwd])["attack"] < full
    
def test_development_keeps_a_players_shape():
    p = Player("X", "FWD", datetime.date(1880, 1, 1), 60, 60)
    shape = {k: v - p.current_ability for k, v in p.attributes.items()}
    p.develop(datetime.date(1896, 6, 1))
    assert {k: v - p.current_ability for k, v in p.attributes.items()} == shape

def _team_with(n_available):
    team = _squad()
    for p in team.squad[n_available:]:
        p.is_injured = True
    return team


def test_team_with_too_few_players_forfeits():
    short, fine = _team_with(6), _squad()
    hg, ag, events, ratings, home_xi, away_xi = simulate_match(short, fine)
    assert (hg, ag) == (0, 3)                         # the short team is the home side
    assert any(e["type"] == "forfeit" for e in events)
    assert home_xi == [] and away_xi == []
    assert all(p.appearances == 0 for p in fine.squad)


def test_matches_with_barely_enough_players_never_crash():
    for _ in range(300):
        hg, ag, *_ = simulate_match(_team_with(8), _team_with(8), season_year="1970/71")
        assert hg >= 0 and ag >= 0

ON = datetime.date(1897, 5, 31)
CFG = {"pa_cap": 200, "wonderkid_pa_cap": 200, "wonderkid_chance": 0.0}


def _youth(position, age, ca=50, pa=70):
    return Player(f"{position}-{age}-{ca}", position, datetime.date(1897 - age, 1, 1), ca, pa)


def test_intake_goes_to_the_youth_team_not_the_first_team():
    team = _squad()
    before = len(team.squad)
    arrivals = youth_intake(team, CFG, 60.0, "1897/98")
    assert len(team.squad) == before
    assert team.youth == arrivals and len(arrivals) > 0
    assert all(15 <= 1897 - p.birth_date.year <= 17 for p in arrivals)


def test_promotion_fills_vacancies_with_the_best_prospect():
    team = _squad()                      # 1 GK, 3 DEF, 4 MID, 6 FWD: short of a GK and a DEF
    gk, df, fwd = _youth("GK", 18), _youth("DEF", 18), _youth("FWD", 18, ca=30)
    team.youth = [gk, df, fwd]
    promoted = ai_promotions(team, ON)
    assert gk in promoted and df in promoted
    assert fwd not in promoted and fwd in team.youth      # no vacancy, not good enough
    assert gk in team.squad and gk not in team.youth


def test_too_young_prospects_are_not_promoted():
    team = _squad()
    kid = _youth("GK", 16)
    team.youth = [kid]
    assert ai_promotions(team, ON) == []
    assert kid in team.youth


def test_overage_youth_are_released():
    team = _squad()
    old = _youth("FWD", 20, ca=30)
    team.youth = [old]
    assert release_overage(team, ON) == [old]
    assert old in team.released and old not in team.youth


def test_promote_and_demote_move_players_between_the_teams():
    team = _squad()
    kid = _youth("MID", 18)
    team.youth = [kid]
    promote(team, kid)
    assert kid in team.squad and kid not in team.youth
    demote(team, kid)
    assert kid in team.youth and kid not in team.squad


def test_save_round_trip_keeps_youth_and_released(tmp_path):
    team = _squad()
    team.youth = [_youth("MID", 17)]
    team.released = [_youth("FWD", 20)]
    path = str(tmp_path / "t.json")
    save_teams_to_file([team], path)
    loaded = load_teams_from_file(path)[0]
    assert [p.id for p in loaded.youth] == [p.id for p in team.youth]
    assert [p.id for p in loaded.released] == [p.id for p in team.released]


def test_save_round_trip_keeps_retired_players(tmp_path):
    team = _squad()
    leaver = team.squad[1]
    leaver.is_retired = True
    retire_players(team, "1896/97")
    path = str(tmp_path / "teams.json")
    save_teams_to_file([team], path)
    loaded = load_teams_from_file(path)[0]
    assert [p.id for p in loaded.retired] == [leaver.id]
    assert loaded.squad[0].attributes == team.squad[0].attributes


def test_world_stays_alive_for_40_seasons(tmp_path):
    engine = make_engine(tmp_path, seasons=40)
    forfeits = 0
    for s in play(engine):
        if s["type"] == "matchday":
            forfeits += sum(1 for r in s["results"] for e in r["events"] if e["type"] == "forfeit")
    assert forfeits <= 2
    for team in engine.teams:
        assert not any(p.is_retired for p in team.squad)
        assert len(team.squad) >= 14
        assert all(t.youth for t in engine.teams)
        
def test_retired_player_keeps_career_history(tmp_path):
    team = _squad()
    p = team.squad[1]
    p.career_history = [{"season": "1896/97", "team": "Old FC"},
                        {"season": "1897/98", "team": "T"}]
    p.is_retired = True
    retire_players(team, "1897/98")
    path = str(tmp_path / "t.json")
    save_teams_to_file([team], path)
    loaded = load_teams_from_file(path)[0]
    assert loaded.retired[0].career_history == p.career_history
    
def test_team_prestige_is_conserved():
    from prestige import update_team_prestige
    teams = [Team(f"T{i}", 60, 60, 60) for i in range(8)]
    for i, t in enumerate(teams):
        t.prestige = 500.0 + 100 * i
    standings = [{"team": t.name} for t in reversed(teams)]    # T7 wins, T0 is last
    before = sum(t.prestige for t in teams)
    for _ in range(50):
        update_team_prestige(teams, standings, 7000.0, {"T0": 40.0})
    assert abs(sum(t.prestige for t in teams) - before) < 5.0
    assert teams[7].prestige > teams[0].prestige               # winners hold more


def test_nation_prestige_is_frozen_while_only_one_nation_plays():
    from prestige import update_nation_prestige
    from data_loader import load_nations
    nations = load_nations()
    before = nations["myria"].prestige
    team = Team("T", 60, 60, 60)
    team.nation_id = "myria"
    log = update_nation_prestige(nations, [team], [{"team": "T"}], 7000.0, {}, {})
    assert log == [] and nations["myria"].prestige == before
    
def test_team_ids_are_stable_slugs(tmp_path):
    engine = make_engine(tmp_path)
    engine.advance()
    ids = {t.id for t in engine.teams}
    assert "kluba_sulhavonos" in ids and len(ids) == len(engine.teams)


def test_ids_survive_save_and_load(tmp_path):
    a = make_engine(tmp_path, seasons=2)
    list(play(a, until=("between_seasons",)))
    b = make_engine(tmp_path, seasons=2)
    b.advance(load_save=True)
    assert [t.id for t in b.teams] == [t.id for t in a.teams]


def test_results_standings_and_history_carry_team_ids(tmp_path):
    engine = make_engine(tmp_path)
    for state in play(engine, until=("season_end",)):
        if state["type"] == "matchday":
            r = state["results"][0]
            assert r["home_team_id"] and r["away_team_id"]
        if state["type"] == "season_end":
            assert all(row["team_id"] for row in state["final_standings"])
    team = engine.teams[0]
    assert team.squad[0].career_history[-1]["team_id"] == team.id
    
def test_season_archive_records_tables_trophies_and_players(tmp_path):
    engine = make_engine(tmp_path, seasons=2)
    list(play(engine))
    arch = engine.archive
    champs = arch.champions("lhiga_alhika")
    assert [c["season"] for c in champs] == ["1896/97", "1897/98"]
    table = arch.table("1896/97", "lhiga_alhika")
    assert len(table) == 8 and table[0]["position"] == 1
    assert table[0]["team_id"] == champs[0]["winner_id"]
    assert sum(r["wins"] for r in table) == sum(r["losses"] for r in table)
    assert arch.champions("kopa_protonas")                    # cup winners are recorded too
    leaders = arch.leaders("goals", 3)
    assert leaders and leaders[0]["total"] >= leaders[-1]["total"]
    assert arch.season_matches("1896/97", "lhiga_alhika")[0]["date"]


def test_writing_a_season_twice_does_not_duplicate(tmp_path, monkeypatch):
    from archive import Archive
    seen = []
    original = Archive.write_season

    def spy(self, payload):
        seen.append(payload)
        return original(self, payload)

    monkeypatch.setattr(Archive, "write_season", spy)
    engine = make_engine(tmp_path)
    list(play(engine))
    engine.archive.write_season(seen[0])                      # the same season again
    assert len(engine.archive.table("1896/97", "lhiga_alhika")) == 8


def test_archive_survives_resume(tmp_path):
    a = make_engine(tmp_path, seasons=3)
    list(play(a, until=("between_seasons",)))
    b = make_engine(tmp_path, seasons=3)
    b.advance(load_save=True)
    assert [c["season"] for c in b.archive.champions("lhiga_alhika")] == ["1896/97"]
    
def test_clubs_join_the_league_in_the_season_they_are_founded(tmp_path):
    engine = make_engine(tmp_path, seasons=4)
    sizes = {}
    for state in play(engine):
        if state["type"] == "season_end":
            sizes[state["season"]] = len(state["final_standings"])
    assert sizes == {"1896/97": 8, "1897/98": 9, "1898/99": 10, "1899/00": 12}


def test_cup_only_clubs_appear_and_play_the_cup(tmp_path):
    engine = make_engine(tmp_path, seasons=12)               # reaches 1907/08
    list(play(engine))
    assert len(engine.cup.teams) > len(engine.comp.teams)
    cup_only = [t for t in engine.teams if engine.comp.key not in t.competitions]
    assert cup_only and all(t.squad for t in cup_only)


def test_new_clubs_are_identical_after_a_resume(tmp_path):
    a = make_engine(tmp_path, seasons=3)
    list(play(a, until=("between_seasons",)))      # 1897/98 is about to start: Gedimou is founded
    b = make_engine(tmp_path, seasons=3)
    b.advance(load_save=True)
    assert [t.id for t in a.teams] == [t.id for t in b.teams]
    assert [p.id for p in a.teams[-1].squad] == [p.id for p in b.teams[-1].squad]