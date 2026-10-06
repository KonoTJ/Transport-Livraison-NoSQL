# generer_donnees.py : génération du jeu de données (partie 1)
import random
import math
from datetime import datetime, timedelta
from config import get_db
from pymongo import UpdateOne

db = get_db()

# --- Listes de valeurs réalistes ---------------------------------------
NOMS = ["Mbarga", "Ngo Bassa", "Fotso", "Atangana", "Njoya", "Ekane",
        "Tchoupo", "Bello", "Kamga", "Nkou", "Ndongo", "Tagne", "Mvondo", "Abena","Donfack","Litchuindem","Acha","Nkeng","Kono"]
PRENOMS = ["Aline", "Paul", "Kevin", "Marie", "Ibrahim", "Sandra", "Rose",
           "Moussa", "Jean", "Brice", "Carine", "Hervé", "Nadine", "Samuel",
           "Jordan","Pavel","Amstrong","Loic","Ivan","Louise","Lina","Brenda","Daniella"]
QUARTIERS = {
    "Douala": ["Akwa", "Bonanjo", "Bonapriso", "Deido", "Bonabéri", "Makepe","Pk17","Nyalla"],
    "Yaoundé": ["Bastos", "Mvan", "Essos", "Mokolo", "Biyem-Assi", "Nlongkak","Soa","Biteng"],
    "Bafoussam": ["Tamdja", "Kamkop", "Djeleng", "Famla"],
    "Dschang": ["Foto", "Foreke", "Minmeto", "Tsinkop","Tchouale","Paid-Ground"],
}
TYPES_VEHICULE = ["moto", "voiture", "camionnette"]
MOYENS_PAIEMENT = ["Orange Money", "MTN Mobile Money", "espèces"]

# code, ville, longitude, latitude, prix_base (FCFA), prix_km (FCFA)
ZONES = [
    ("ZON-01", "Douala",    9.7679,  4.0511, 500, 150),
    ("ZON-02", "Douala",    9.6700,  4.0700, 450, 140),
    ("ZON-03", "Yaoundé",  11.5021,  3.8480, 500, 150),
    ("ZON-04", "Bafoussam", 10.4179, 5.4737, 400, 120),
    ("ZON-05", "Dschang",   13.3984,  9.3015, 400, 120),
]


def date_aleatoire(debut, fin):
    """Renvoie une date au hasard entre debut et fin."""
    return debut + timedelta(days=random.randint(0, (fin - debut).days))


def position_autour(lon, lat, rayon=0.03):
    """Point GeoJSON proche d'un centre. Ordre GeoJSON : [longitude, latitude]."""
    return {"type": "Point",
            "coordinates": [round(lon + random.uniform(-rayon, rayon), 5),
                            round(lat + random.uniform(-rayon, rayon), 5)]}


def telephone():
    return f"6{random.randint(50000000, 99999999)}"


# --- Génération --------------------------------------------------------
def generer_zones():
    zones = []
    for code, ville, lon, lat, base, km in ZONES:
        zones.append({
            "code": code,
            "ville": ville,
            "centre": {"type": "Point", "coordinates": [lon, lat]},
            "prix_base": base,
            "prix_km": km,
            "majoration_pointe": {"heures": [[7, 9], [17, 20]], "coefficient": 1.3},
        })
    db.zones.delete_many({})
    db.zones.insert_many(zones)
    print(len(zones), "zones insérées")
    return zones


def generer_chauffeurs(zones, nombre):
    chauffeurs = []
    for i in range(1, nombre + 1):
        zone = random.choice(zones)
        lon, lat = zone["centre"]["coordinates"]
        documents = [
            {"type": t, "date_expiration": date_aleatoire(datetime(2025, 6, 1),
                                                         datetime(2029, 12, 31))}
            for t in ["permis", "assurance", "carte_grise"]
        ]
        chauffeurs.append({
            "code": f"CHF-{i:04d}",
            "nom": random.choice(NOMS),
            "prenom": random.choice(PRENOMS),
            "telephone": telephone(),
            "numero_permis": f"PERM-{i:05d}",
            "zone": zone["code"],
            "statut": random.choices(["disponible", "en_course", "hors_ligne"],
                                     weights=[50, 20, 30])[0],
            "note_moyenne": 0,     # recalculée après les évaluations
            "nb_courses": 0,       # recalculé après les courses
            "vehicule": {"type": random.choice(TYPES_VEHICULE),
                         "immatriculation": f"LT-{i:03d}-{random.choice('ABCDEF')}{random.choice('ABCDEF')}"},
            "position": position_autour(lon, lat),
            "documents": documents,
        })
    db.chauffeurs.delete_many({})
    db.chauffeurs.insert_many(chauffeurs)
    print(len(chauffeurs), "chauffeurs insérés")
    return chauffeurs


def generer_clients(zones, nombre):
    clients = []
    for i in range(1, nombre + 1):
        adresses = []
        for libelle in random.sample(["Maison", "Travail", "Marché", "École"],
                                     k=random.randint(1, 3)):
            zone = random.choice(zones)
            lon, lat = zone["centre"]["coordinates"]
            adresses.append({
                "libelle": libelle,
                "adresse": f"{random.choice(QUARTIERS[zone['ville']])}, {zone['ville']}",
                "position": position_autour(lon, lat),
            })
        clients.append({
            "code": f"CLI-{i:04d}",
            "nom": random.choice(NOMS),
            "prenom": random.choice(PRENOMS),
            "telephone": telephone(),
            "moyen_paiement": random.choice(MOYENS_PAIEMENT),
            "adresses_favorites": adresses,
        })
    db.clients.delete_many({})
    db.clients.insert_many(clients)
    print(len(clients), "clients insérés")
    return clients

# --- Partie 2 : courses, paiements, évaluations -------------------------

def distance_km(p1, p2):
    """Distance à vol d'oiseau entre deux points GeoJSON (formule de haversine)."""
    lon1, lat1 = p1["coordinates"]
    lon2, lat2 = p2["coordinates"]
    r = 6371
    a1, a2 = math.radians(lat1), math.radians(lat2)
    da = a2 - a1
    do = math.radians(lon2 - lon1)
    h = math.sin(da / 2) ** 2 + math.cos(a1) * math.cos(a2) * math.sin(do / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def est_heure_de_pointe(zone, date):
    """Vrai si l'heure de la date tombe dans une tranche de pointe de la zone."""
    return any(debut <= date.hour < fin
               for debut, fin in zone["majoration_pointe"]["heures"])


def calculer_prix(zone, distance, date):
    """prix = base + km × distance, multiplié par le coefficient en heure de pointe."""
    prix = zone["prix_base"] + zone["prix_km"] * distance
    if est_heure_de_pointe(zone, date):
        prix *= zone["majoration_pointe"]["coefficient"]
    return int(round(prix))


def date_course():
    """Date au hasard sur 12 mois, avec plus de courses aux heures de pointe."""
    jour = date_aleatoire(datetime(2025, 10, 1), datetime(2026, 9, 30))
    poids_heures = [1, 1, 1, 1, 1, 2, 4, 9, 9, 5, 4, 4, 5, 5, 4, 4, 5, 9, 9, 8, 5, 3, 2, 1]
    heure = random.choices(range(24), weights=poids_heures)[0]
    return jour.replace(hour=heure, minute=random.randint(0, 59))


def generer_courses(zones, chauffeurs, clients, nombre):
    zones_par_code = {z["code"]: z for z in zones}
    # Popularité inégale : certains chauffeurs font beaucoup plus de courses
    poids = [random.choice([1] * 60 + [3] * 30 + [6] * 10) for _ in chauffeurs]
    vitesses = {"moto": 25, "voiture": 20, "camionnette": 18}   # km/h en ville

    courses = []
    for i in range(1, nombre + 1):
        chauffeur = random.choices(chauffeurs, weights=poids)[0]
        zone = zones_par_code[chauffeur["zone"]]
        client = random.choice(clients)
        lon, lat = zone["centre"]["coordinates"]

        depart = {"adresse": f"{random.choice(QUARTIERS[zone['ville']])}, {zone['ville']}",
                  "position": position_autour(lon, lat)}
        arrivee = {"adresse": f"{random.choice(QUARTIERS[zone['ville']])}, {zone['ville']}",
                   "position": position_autour(lon, lat)}
        dist = max(round(distance_km(depart["position"], arrivee["position"]), 1), 0.8)
        type_veh = chauffeur["vehicule"]["type"]
        duree = max(5, int(dist / vitesses[type_veh] * 60) + random.randint(2, 8))
        date = date_course()

        courses.append({
            "code": f"CRS-{i:05d}",
            "type": random.choices(["personne", "colis"], weights=[70, 30])[0],
            "client": client["code"],
            "chauffeur": chauffeur["code"],
            "zone": zone["code"],
            "ville": zone["ville"],              # copiée : doit rester vraie
            "type_vehicule": type_veh,           # copié
            "depart": depart,
            "arrivee": arrivee,
            "distance_km": dist,
            "duree_estimee_min": duree,
            "prix": calculer_prix(zone, dist, date),   # copié : prix réellement facturé
            "statut": random.choices(
                ["terminee", "annulee", "en_cours", "acceptee", "demandee"],
                weights=[85, 8, 3, 2, 2])[0],
            "date": date,
            "mode_paiement": client["moyen_paiement"],  # copié pour les agrégations
        })
    db.courses.delete_many({})
    db.courses.insert_many(courses)
    print(len(courses), "courses insérées")
    return courses


def generer_paiements(courses):
    """Un paiement par course terminée (relation 0..1 de la course vers le paiement)."""
    paiements = []
    for c in courses:
        if c["statut"] != "terminee":
            continue
        paiements.append({
            "course": c["code"],
            "montant": c["prix"],
            "methode": c["mode_paiement"],       # identique à la course
            "statut": random.choices(["valide", "echoue", "en_attente"],
                                     weights=[92, 3, 5])[0],
            "date": c["date"] + timedelta(minutes=c["duree_estimee_min"] + random.randint(1, 15)),
        })
    db.paiements.delete_many({})
    db.paiements.insert_many(paiements)
    print(len(paiements), "paiements insérés")
    return paiements


def generer_evaluations(courses, nombre):
    """Évaluations sur un échantillon de courses terminées (relation 0..1)."""
    terminees = [c for c in courses if c["statut"] == "terminee"]
    echantillon = random.sample(terminees, k=min(nombre, len(terminees)))
    commentaires = ["Course rapide", "Très ponctuel", "Chauffeur aimable", "Un peu long",
                    "Conduite prudente", "Parfait", "Client courtois", ""]
    evaluations = []
    for c in echantillon:
        evaluations.append({
            "course": c["code"],
            "chauffeur": c["chauffeur"],          # copié pour éviter un $lookup
            "client": c["client"],
            "note_chauffeur": random.choices([1, 2, 3, 4, 5], weights=[3, 5, 12, 35, 45])[0],
            "note_client": random.choices([1, 2, 3, 4, 5], weights=[2, 4, 14, 35, 45])[0],
            "commentaire": random.choice(commentaires),
            "date": c["date"] + timedelta(minutes=c["duree_estimee_min"] + random.randint(5, 120)),
        })
    db.evaluations.delete_many({})
    db.evaluations.insert_many(evaluations)
    print(len(evaluations), "évaluations insérées")
    return evaluations


def recalculer_stats_chauffeurs():
    """Met à jour nb_courses et note_moyenne à partir des vraies données."""
    nb = {d["_id"]: d["n"] for d in db.courses.aggregate([
        {"$match": {"statut": "terminee"}},
        {"$group": {"_id": "$chauffeur", "n": {"$sum": 1}}}])}
    notes = {d["_id"]: round(d["m"], 2) for d in db.evaluations.aggregate([
        {"$group": {"_id": "$chauffeur", "m": {"$avg": "$note_chauffeur"}}}])}
    operations = [
        UpdateOne({"code": ch["code"]},
                  {"$set": {"nb_courses": nb.get(ch["code"], 0),
                            "note_moyenne": notes.get(ch["code"], 0)}})
        for ch in db.chauffeurs.find({}, {"code": 1})
    ]
    db.chauffeurs.bulk_write(operations)
    print("Statistiques des chauffeurs recalculées")


def tout_generer():
    """Génère toute la base (appelée par le menu ou en ligne de commande)."""
    random.seed(42)                       # mêmes données à chaque lancement
    db.evaluations_archives.drop()        # repart sans archive de test
    zones = generer_zones()
    chauffeurs = generer_chauffeurs(zones, 100)
    clients = generer_clients(zones, 300)
    courses = generer_courses(zones, chauffeurs, clients, 1200)
    generer_paiements(courses)
    generer_evaluations(courses, 900)
    recalculer_stats_chauffeurs()


if __name__ == "__main__":
    tout_generer()