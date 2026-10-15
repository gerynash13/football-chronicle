from collections import Counter
from data_loader import (_read_yaml, load_nations, load_teams,
                         load_competitions, load_journalists)

def validate() -> list[str]:
    errors = []
    raw = _read_yaml("nations.yaml")
    
    for i, c in Counter(n["id"] for n in raw).items():
        if c > 1:
            errors.append(f"Duplicate nation ID: {i}")
    for i, c in Counter(r["id"] for n in raw for r in n.get("regions", [])).items():
        if c > 1:
            errors.append(f"Duplicate region ID: {i}")
            
    nations, comps = load_nations(), load_competitions()
    for t in load_teams().values():
        if t.nation_id not in nations:
            errors.append(f"team {t.id}: unknown nation '{t.nation_id}'")
            continue
        regions = {r.id for r in nations[t.nation_id].regions}
        if t.home_region not in regions:
            errors.append(f"team {t.id}: unknown home region '{t.home_region}'")
        for c in t.competitions:
            if c not in comps:
                errors.append(f"team {t.id}: unknown competition '{c}'")
                
    team_names = {t.name for t in load_teams().values()}
    for j in load_journalists().values():
        if j.nation_id and j.nation_id not in nations:
            errors.append(f"journalist {j.id}: unknown nation '{j.nation_id}'")
        if j.favorite_team and j.favorite_team not in team_names:
            errors.append(f"journalist {j.id}: unknown favorite team '{j.favorite_team}'")

    return errors

if __name__ == "__main__":
    errs = validate()
    print("\n".join(errs) if errs else "Data OK")
    raise SystemExit(1 if errs else 0)