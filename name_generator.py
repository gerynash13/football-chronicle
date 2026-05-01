from classes import Player
import random

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
  
def generate_squad(team_name, average_ca=70):
  squad = []
  
  # Generate 2 goalkeepers
  for i in range(2):
    name = generate_myrian_name()
    age = random.randint(17, 38)
    ca = average_ca + random.randint(-10, 10)
    pa = ca + random.randint(0, 20)
    squad.append(Player(name, "GK", age, ca, pa))
    
  # Generate 4 defenders
  for i in range(4):
    name = generate_myrian_name()
    age = random.randint(17,38)
    ca = average_ca + random.randint(-10, 10)
    pa = ca + random.randint(0,20)
    squad.append(Player(name, "DEF", age, ca, pa))
    
  # Generate 4 midfielders
  for i in range(4):
    name = generate_myrian_name()
    age = random.randint(17, 38)
    ca = average_ca + random.randint(-10, 10)
    pa = ca + random.randint(0, 20)
    squad.append(Player(name, "MID", age, ca, pa))
    
  # Generate 6 forwards
  for i in range(6):
    name = generate_myrian_name()
    age = random.randint(17, 38)
    ca = average_ca + random.randint(-10, 10)
    pa = ca + random.randint(0, 20)
    squad.append(Player(name, "FWD", age, ca, pa))
    
  return squad