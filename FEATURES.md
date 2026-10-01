# FEATURES.md
# Feature tracking for the football management simulation
# Updated as features are completed or reprioritised

# STATUS LABELS
# [done]      - implemented and tested
# [in-progress] - currently being built
# [next]      - foundational, do before moving on
# [soon]      - do before or alongside first UI version
# [later]     - additive, can slot in at any stage
# [v2]        - complex, requires earlier systems to be complete first


## FOUNDATION (must be right before building on top)

- [done]      Player class with birth_date, nationality, preferred_foot,
              contract_expires, wage, is_retired
- [done]      YAML data layer — nations.yaml, teams.yaml, competitions.yaml
- [done]      data_loader.py — reads YAML, exposes typed config objects
- [done]      GameEngine — state machine separating logic from presentation
- [done]      CLI view (main.py) consuming engine state dicts
- [done]      CupCompetition — simulate_cup_round, advance_cup_winner,
              draw handling, schedule_replay
- [done]      Test suite — test_cup.py (12 tests)
- [done]      Prestige schema — 0-10000 scale, tier derived from prestige,
              decay, upset multiplier, competition prestige values
              (schema designed, runtime logic not yet implemented)

- [done]      Region system
                nations.yaml  → 4 named regions per nation
                teams.yaml    → home_region per team
                player.py     → birth_region field
                data_manager  → save/load birth_region
                name_generator → assign birth_region from team region

- [done]      Budget system
                team.py       → budget, wage_budget fields
                teams.yaml    → starting budget per team
                data_manager  → save/load budget fields

- [done]      News feed foundation (event capture layer only — not articles)
                NewsFeed class in engine
                publish() hooks in simulation, competition, engine
                relevance tiers: global | regional | local
                stored as structured events, consumed by news generator later

- [done]      Engine smoke test — verify full season runs without errors

- [done]      Prestige runtime logic
                season-end prestige update (league contribution)
                upset multiplier on competition wins
                cumulative decay with floor
                tier change with min_seasons guard

- [done]      Cup competition wired into calendar
                CupCompetition created in _start_season
                midweek scheduling
                cup teams drawn from teams.yaml (all_members)

- [done]      Supercup — league winner vs cup winner, end of season


## UI LAYER

- [done]      Flask API (api.py)
                POST /api/advance    → engine.advance()
                POST /api/choose     → engine.choose(index)
                GET  /api/state      → current state without advancing
                GET  /api/inbox      → calendar inbox items

- [in-progress]      Basic HTML/CSS/JS frontend
                Season overview page
                Matchday results view
                League table
                Blocking event handler (choices UI)
                Player list / basic player card


## COMPETITION SYSTEMS

- [later]     Second division + promotion/relegation
- [later]     British Home Championship (end_of_season timing, 4 nations)
- [later]     Olympic Football Tournament (1908, every 4 years, summer)
- [later]     FIFA World Cup (1930, every 4 years, summer)
- [later]     European club competition (Champions League equivalent, ~1955)
- [later]     Nations qualifying system for international competitions
- [later]     Squad number assignment gated by season year (>= 1928)


## TRANSFER MARKET

- [later]     Basic transfer system
                AI clubs identify squad weaknesses
                make offers for players
                player acceptance based on project fit + wage
- [later]     Transfer window (open/closed periods)
- [later]     Transfer listing and transfer requests
- [later]     Loan system
- [later]     Free agent pool
- [later]     Player values (2 hidden attributes revealed through scouting)
- [later]     Club project / "convince to sign" system


## SCOUTING SYSTEM

- [later]     Scout assignments — send to region, return report after N weeks
- [later]     Scouting knowledge — 0–100% per region, unlocks player values
- [later]     Scout attributes — affects speed and accuracy of reports
- [later]     Scout cost — deducted from budget
- [later]     "Discovered in the park" rare event (scout returns unexpected talent)
- [later]     Scouting interest effect on player morale / form
              (big club interest can inspire or pressurise a player)


## YOUTH ACADEMY

- [later]     Academy intake system — replaces generate_squad() for youth
- [later]     Regional scouting for academy (home region first,
              then national, then manager/owner origin region)
- [later]     Academy actions with diminishing returns
              (some once-per-season, some once-per-player)
              cost scaled by prestige gap and player nationality
- [later]     Club culture — defines preferred signing profile
              (region, style of play, etc.)
- [later]     Rival club competition for academy prospects
- [later]     Regional talent level shifts based on competition success
              (a region that produces a champion sees a youth surge)


## NEWS AND MEDIA SYSTEM

- [later]     News generator — turns NewsFeed events into articles
- [later]     News source tiers
                tier 1: high-quality journalism (insightful, reliable)
                tier 2: tabloids (sensationalist, sometimes inaccurate)
                tier 3: social media accounts (fast, often wrong,
                        source of drama and fake transfer rumours)
- [later]     Journalist personalities
                favourite teams (biased coverage)
                writing style (analytical / dramatic / gossipy)
                reliability score (affects how often their stories are true)
- [later]     News filtering
                global  — major events worldwide
                regional — teams in same geographic area
                local   — teams in same league / rival clubs
- [later]     Player media page — all articles written about a player,
              hinting at personality without fully revealing it
- [later]     Media hype system — generated players can be overhyped,
              leading to inflated expectations and potential disappointment
- [later]     Club-controlled media — user can leak stories,
              unsettle rivals, announce scouting interest strategically


## PLAYER SYSTEMS

- [later]     Retirement system — probability increases after age 35 or after severe injury,
              triggers is_retired flag (field exists, logic not yet wired)
- [later]     Player personality traits (professional, temperamental,
              leader, homesick, ambitious, etc.)
- [later]     Locker room harmony / conflict system
- [later]     Mentorship events — veteran offers to mentor young player
- [later]     Player goals and promises — track what was promised,
              affect morale if broken
- [later]     Player press conferences and public statements


## IN-GAME EVENTS (calendar system)

Partially implemented (Event, Choice, Effect classes exist):

- [later]     Player interaction events (more variety)
                wants more playing time
                wants new contract
                wants to leave (triggers transfer request)
                falling out with teammate
                development surge announcement
                return from injury in great form

- [later]     Transfer market events
                AI offer for your player
                agent calls (player wants to leave, agent offers player to club, etc)
                bargain player released
                rival signs player you were tracking

- [later]     Club and world flavour events
                rival club internal crisis (manager sacked, star injured)
                weather affecting upcoming match
                benefactor investment offer
                stadium atmosphere boost (derby week)
                fixture rescheduled

- [later]     Competition events
                opponent key player suspended for your next match
                referee controversy (press coverage)

- [later]     Longer-arc events
                league format change (federation decision)
                economic depression (lower transfer budgets league-wide)
                rival fire sale after prolonged poor form
                political events affecting international travel


## TACTICS SYSTEM

- [v2]        Formation selection (affects starting XI logic)
- [v2]        Playing style attributes (pressing intensity, tempo,
              width, defensive line height)
- [v2]        Style-vs-style match modifier in simulate_match()
- [v2]        Tactical evolution over decades
              (new ideas emerge, spread through the game world,
              coaches who resist may fall behind or find an edge)


## MATCH ENGINE

- [later]     Home/away form differentiation
- [later]     Weather effects on match — heavy rain reduces
              high-passing team effectiveness
- [later]     Derby / rivalry boost to atmosphere and performance
- [v2]        Tactics feeding into simulation


## WORLD SIMULATION

- [later]     AI club management — squad building, transfers, hiring
- [later]     Manager hiring and sacking (AI clubs)
- [later]     Club financial model — revenue, wages, debt
- [v2]        Tactical evolution — new styles emerge from successful coaches
- [v2]        Political/economic world events affecting football


## PRESENTATION

- [later]     Weekly recap at end of matchday
              (league results, stats, awards, power rankings)
- [later]     Kit system — changes each season, respects club colours
- [v2]        AI-generated player backstories based on personality + origin
- [v2]        AI-generated unique player interactions
              (uses Anthropic API, stores conversation history,
              creates personality continuity across seasons)