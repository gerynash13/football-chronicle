from classes import Player
from nations import get_nation_config
import random
import datetime

def _random_birth_date(birth_year: int) -> datetime.date:
  # Have to update it later to include days 29-31 depending on month
  return datetime.date(
    birth_date,
    random.randint(1, 12),
    random.randint(1, 28)
  )

MYRIAN_NAMES = [
    "Nikolvar", "Andrevos", "Aleksalhos", "Demetralhos", "Ioannalhos", "Georvos", 
    "Stefanhos", "Kostanvar", "Filipalhos", "Teodvar", "Mikhavar", "Kyrialhos", 
    "Vasilhos", "Grigoralhos", "Panaghos", "Apostolhos", "Evaggelhos", "Stavralhos", 
    "Haralhos", "Athanasvar", "Leonardhos", "Manolhos", "Spyrolhos", "Eustrathos", 
    "Kiriakhos", "Konstantvar", "Theophihos", "Pantazalhos", "Nikephvar", "Kallistratos", 
    "Protopalhos", "Aristalhos", "Alexandropalhos", "Christofalhos", "Dimitriadvar", 
    "Georgalhos", "Nikoforvar", "Filippalhos", "Anastasvar", "Konstantalhos", "Savalhos", 
    "Timotealhos", "Vitaros", "Santhon", "Laurivos", "Aurelvar", "Maximalhos", "Silvaros", 
    "Dominalhos", "Sivanos", "Victorvar", "Julalhos", "Klaudvar", "Lucivar", "Markelhos", 
    "Adrianos", "Fortunatos", "Liberatos", "Klementos", "Placidos", "Sergivar", 
    "Valentinos", "Florivos", "Karmelos", "Donatos", "Ambrosvar", "Benidiktos", 
    "Augustalhos", "Benedikvar", "Celestinos", "Dominicvar", "Felicianos", "Justinianhos", 
    "Marcellinhos", "Valerianhos", "Victorinhos", "Laurentinhos", "Peros", "Bernalhos", 
    "Arnalhos", "Guilhon", "Ramhos", "Jordavar", "Rikalhos", "Ferranhos", "Olivar", 
    "Bertavar", "Jaumelhos", "Ponselhos", "Dalmauhos", "Guerauhos", "Huguelhos", 
    "Llorenhos", "Mateuhos", "Vicenthos", "Gaietahos", "Mundilhos", "Franseschos", 
    "Blailhos", "Gilaberthos", "Perelhos", "Miquehos", "Bernatvar", "Ramhona", "Sulhon", 
    "Veldhir", "Tolvhan", "Bralhor", "Alhvan", "Pirnalh", "Tornalh", "Emhavar", 
    "Dolvhan", "Gorulh", "Dravon", "Galvon", "Arnhon", "Pelhvar", "Murnon", "Drosvon", 
    "Talvon", "Pethor", "Nalhon", "Orlhon", "Emvhon", "Brakhor", "Sulhvar", "Galvhor", 
    "Drosvhar", "Tralvon", "Pelhon", "Veldhor", "Kalvon", "Arnhelh", "Yitzhak", 
    "Shlomo", "Avraham", "Moshe", "David", "Yaakov", "Yosef", "Binyamin", "Eliyahu", 
    "Shimon", "Natan", "Aron", "Levi", "Meir", "Haim", "Ezra", "Efraim", "Gideon", 
    "Reuven", "Asher", "Shaul", "Barukh", "Mordekhai", "Marcalhos", "Giovanavar", 
    "Brunavar", "Matteohos", "Enricohos", "Cesarhos", "Albertohos", "Renzohos", 
    "Giacomohos", "Anselmohos", "Luigivar", "Benedettohos"
]

MYRIAN_SURNAMES = [
    "Sulhanos", "Kalveira", "Emvarios", "Brakhos", "Murnelos", "Arnhelos", "Pethanos", 
    "Drosveira", "Tornheiros", "Goruveira", "Orlhanos", "Galveiros", "Dravanos", 
    "Talvanos", "Veldheiros", "Pelheiros", "Emvhalhos", "Brakhalhos", "Arnheiros", 
    "Nalhanos", "Sulheiros", "Toranos", "Kalpeiros", "Veldhanos", "Drosvanos", 
    "Galvonhos", "Brakeiros", "Pethalhos", "Murnanos", "Emhalhos", "Tralvanos", 
    "Arnhalos", "Galvhalhos", "Sulhonhos", "Veldhalhos", "Kalvanos", "Tolvheiros", 
    "Drosvhalhos", "Petalhos", "Kalphos", "Marivar", "Mercavar", "Pescavar", "Talhavar", 
    "Fustaveira", "Portavar", "Jurikavar", "Nauavar", "Nalhavar", "Talvavar", 
    "Emvaravar", "Ferraavar", "Pedraavar", "Vidravar", "Teixavar", "Argentavar", 
    "Molnavar", "Fornavar", "Pastavar", "Boteravar", "Sartravar", "Pintavar", 
    "Caldavar", "Lapidavar", "Carnavar", "Marivavar", "Brakavar", "Pelhavar", 
    "Salavar", "Canaavar", "Teravar", "Mielavar", "Vinavar", "Oleiavar", "Fustavar", 
    "Terranos", "Dominalhar", "Templarhos", "Belavar", "Santhavar", "Vitavar", 
    "Lunivar", "Solivar", "Juravar", "Terravar", "Montalvar", "Sylvavar", "Campavar", 
    "Valavar", "Fontavar", "Petravar", "Lacavar", "Insulavar", "Arcavar", "Maragavar", 
    "Rioavar", "Saxavar", "Murnikos", "Kalvōdēs", "Veldhikos", "Kardianos", "Megistos", 
    "Mikranos", "Arnhikos", "Pethikos", "Glykanos", "Talvikos", "Orhlhikos", 
    "Galvikos", "Dravikos", "Brakikos", "Emvarikos", "Sulhikos", "Arnhōdēs", "Murnōdēs", 
    "Nalhikos", "Drosvikos", "Goruvikos", "Thalassikos", "Pyrikanos", "Veldhōdēs", 
    "Talvōdēs", "Petroikos", "Galvōdēs", "Tornhikos", "Emvhalikos", "Bouleutar", 
    "Senhoravar", "Sankavar", "Phylakavar", "Nomikavar", "Archavar", "Konsulavar", 
    "Eforavar", "Grammatavar", "Logothavar", "Tameiavar", "Stratigavar", "Notaravar", 
    "Kancilavar", "Protokolavar", "Synedriavar", "Papadopalhos", "Angelidvar", 
    "Karageorvos", "Athinaios", "Ioannidvar", "Vasiliadvar", "Panagiotopalhos", 
    "Ekonomidvar", "Hatzipalhos", "Korinthios", "Lucivar", "Mercelhar"
]

def generate_myrian_name():
  return(f"{random.choice(MYRIAN_NAMES)} {random.choice(MYRIAN_SURNAMES)}")

def _apply_pa_cap(pa, nation_config):
  """
  Applies the nation's PA cap to the given PA value.
  Has a small wonderkid chance to boost PA up to the wonderkid PA cap.
  Returns the capped PA value and a boolean indicating if the player is a wonderkid.
  """
  if random.random() < nation_config["wonderkid_chance"]:
    return min(pa, nation_config["wonderkid_pa_cap"]), True
  return min(pa, nation_config["pa_cap"]), False
  
def generate_squad(team_name, average_ca=70, nation="Myria", season_year=None):
  nation_config = get_nation_config(nation)
  squad = []
  
  if season_year:
    ref_year = int(season_year.split("/")[0])
  else:
    ref_year = datetime.datetime.now().year
    
  nation_id = nation.lower()
  
  positions = [
    ("GK", 2),
    ("DEF", 4),
    ("MID", 4),
    ("FWD", 6)
  ]
  
  for position, count in positions:
    for _ in range(count):
      name = generate_myrian_name()
      age = random.randint(17, 38)
      birth_year = ref_year - age
      birth_date = _random_birth_date(birth_year)
      
      ca = max(1, int(random.gauss(average_ca, 10)))
      raw_pa = ca + random.randint(0, 20)
      
      pa, is_wonderkid = _apply_pa_cap(raw_pa, nation_config)
      ca = min(ca, pa)  # Ensure CA does not exceed PA after capping
      
      player = Player(
        name=name,
        position=position,
        birth_date=birth_date,
        current_ability=ca,
        potential_ability=pa,
        nationality=nation_id,
      )
      if is_wonderkid:
        player.is_wonderkid = True
      squad.append(player)
      
  # Squad numbers: only assign in seasons where they historically exist (1928-)
  if season_year and int(season_year.split("/")[0]) >= 1928:
    nums = list(range(1, len(squad) + 1))
    random.shuffle(nums)
    # Ensure GK gets number 1
    gks = [p for p in squad if p.position == "GK"]
    if gks:
      try:
        idx = squad.index(gks[0])
        one_idx = nums.index(1)
        nums[idx], nums[one_idx] = nums[one_idx], nums[idx]
      except ValueError:
        pass
      
    for p, n in zip(squad, nums):
      p.squad_number = n
      
  return squad