# crud.py : opérations Créer / Lire / Modifier / Supprimer du Projet 4
from datetime import datetime, timedelta
from pymongo.errors import DuplicateKeyError, PyMongoError

# Enchaînement autorisé des statuts d'une course
SUITE_STATUTS = {"demandee": "acceptee", "acceptee": "en_cours", "en_cours": "terminee"}
VILLES = ["Douala", "Yaoundé", "Bafoussam", "Dschang"]


# ======================= OUTILS =======================================
def verifier_position(lon, lat):
    """Refuse une position hors des limites géographiques."""
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Position invalide : longitude [-180;180], latitude [-90;90].")


def calculer_prix(zone, distance_km, date):
    """prix = base + km × distance, multiplié par le coefficient en heure de pointe."""
    prix = zone["prix_base"] + zone["prix_km"] * distance_km
    if any(d <= date.hour < f for d, f in zone["majoration_pointe"]["heures"]):
        prix *= zone["majoration_pointe"]["coefficient"]
    return int(round(prix))


def prochain_code_course(db):
    """Renvoie le prochain code libre : CRS-00001, CRS-00002..."""
    derniere = db.courses.find_one({}, {"code": 1}, sort=[("code", -1)])
    numero = int(derniere["code"].split("-")[1]) + 1 if derniere else 1
    return f"CRS-{numero:05d}"


# ======================= CRÉER ========================================
def creer_course(db, code_client, code_chauffeur, type_course, depart, arrivee, distance_km):
    """Crée une course : copie ville, véhicule et prix, calcule le prix selon la zone."""
    if type_course not in ("personne", "colis"):
        raise ValueError("Type de course invalide : 'personne' ou 'colis'.")
    if distance_km <= 0:
        raise ValueError("La distance doit être positive.")
    client = db.clients.find_one({"code": code_client})
    chauffeur = db.chauffeurs.find_one({"code": code_chauffeur})
    if not client or not chauffeur:
        raise LookupError("Client ou chauffeur introuvable.")
    if chauffeur["statut"] != "disponible":
        raise ValueError("Ce chauffeur n'est pas disponible.")
    zone = db.zones.find_one({"code": chauffeur["zone"]})
    maintenant = datetime.now()
    course = {
        "code": prochain_code_course(db),
        "type": type_course,
        "client": code_client, "chauffeur": code_chauffeur, "zone": zone["code"],
        "ville": zone["ville"],                         # copiée
        "type_vehicule": chauffeur["vehicule"]["type"],  # copié
        "depart": depart, "arrivee": arrivee,
        "distance_km": distance_km,
        "duree_estimee_min": max(5, int(distance_km * 3)),
        "prix": calculer_prix(zone, distance_km, maintenant),  # copié
        "statut": "demandee", "date": maintenant,
        "mode_paiement": client["moyen_paiement"],
    }
    try:
        db.courses.insert_one(course)
    except DuplicateKeyError:
        raise ValueError("Code de course déjà utilisé.")
    return course["code"]


# ======================= LIRE =========================================
def chauffeurs_disponibles(db, code_zone):
    """Chauffeurs disponibles d'une zone."""
    return list(db.chauffeurs.find({"zone": code_zone, "statut": "disponible"},
                                   {"_id": 0, "code": 1, "nom": 1, "prenom": 1, "vehicule": 1}))


def courses_client(db, code_client):
    """Courses d'un client, de la plus récente à la plus ancienne."""
    return list(db.courses.find({"client": code_client}, {"_id": 0}).sort("date", -1))


def historique_chauffeur(db, code_chauffeur):
    """Courses et évaluations d'un chauffeur."""
    if not db.chauffeurs.find_one({"code": code_chauffeur}):
        raise LookupError(f"Chauffeur {code_chauffeur} introuvable.")
    courses = list(db.courses.find({"chauffeur": code_chauffeur}, {"_id": 0}).sort("date", -1))
    evaluations = list(db.evaluations.find({"chauffeur": code_chauffeur}, {"_id": 0}))
    return courses, evaluations


def courses_par_statut(db, statut):
    """Courses ayant un statut donné."""
    return list(db.courses.find({"statut": statut}, {"_id": 0}))


def chauffeurs_documents_expires(db):
    """Chauffeurs dont au moins un document est expiré."""
    return list(db.chauffeurs.find(
        {"documents": {"$elemMatch": {"date_expiration": {"$lt": datetime.now()}}}},
        {"_id": 0, "code": 1, "nom": 1, "documents": 1}))


# ======================= MODIFIER =====================================
def maj_position(db, code_chauffeur, lon, lat):
    """Met à jour la position GeoJSON d'un chauffeur."""
    verifier_position(lon, lat)
    res = db.chauffeurs.update_one(
        {"code": code_chauffeur},
        {"$set": {"position": {"type": "Point", "coordinates": [lon, lat]}}})
    if res.matched_count == 0:
        raise LookupError(f"Chauffeur {code_chauffeur} introuvable.")


def changer_disponibilite(db, code_chauffeur, statut):
    """Change le statut d'un chauffeur."""
    if statut not in ("disponible", "en_course", "hors_ligne"):
        raise ValueError("Statut invalide.")
    res = db.chauffeurs.update_one({"code": code_chauffeur}, {"$set": {"statut": statut}})
    if res.matched_count == 0:
        raise LookupError(f"Chauffeur {code_chauffeur} introuvable.")


def avancer_statut_course(db, code_course):
    """Fait avancer une course d'un cran et garde chauffeur et paiement cohérents."""
    course = db.courses.find_one({"code": code_course})
    if not course:
        raise LookupError(f"Course {code_course} introuvable.")
    nouveau = SUITE_STATUTS.get(course["statut"])
    if not nouveau:
        raise ValueError(f"Une course '{course['statut']}' ne peut plus avancer.")
    # Le filtre sur l'ancien statut évite un double passage simultané
    res = db.courses.update_one({"code": code_course, "statut": course["statut"]},
                                {"$set": {"statut": nouveau}})
    if res.modified_count == 0:
        raise ValueError("Le statut a déjà été modifié par un autre traitement.")
    if nouveau == "acceptee":
        db.chauffeurs.update_one({"code": course["chauffeur"]}, {"$set": {"statut": "en_course"}})
    elif nouveau == "terminee":
        db.chauffeurs.update_one({"code": course["chauffeur"]},
                                 {"$set": {"statut": "disponible"}, "$inc": {"nb_courses": 1}})
        db.paiements.update_one(     # crée le paiement s'il n'existe pas encore
            {"course": code_course},
            {"$setOnInsert": {"montant": course["prix"], "methode": course["mode_paiement"],
                              "statut": "en_attente", "date": datetime.now()}},
            upsert=True)
    return nouveau


def confirmer_paiement(db, code_course):
    """Passe le paiement d'une course de 'en_attente' (ou 'echoue') à 'valide'."""
    res = db.paiements.update_one({"course": code_course, "statut": {"$ne": "valide"}},
                                  {"$set": {"statut": "valide", "date": datetime.now()}})
    if res.matched_count == 0:
        raise LookupError("Paiement introuvable ou déjà validé.")


# ======================= SUPPRIMER / ARCHIVER =========================
def supprimer_courses_annulees(db):
    """Supprime les courses annulées (elles n'ont ni paiement ni évaluation)."""
    return db.courses.delete_many({"statut": "annulee"}).deleted_count


def archiver(db, collection, filtre):
    """Déplace les documents du filtre vers <collection>_archives."""
    documents = list(db[collection].find(filtre))
    if not documents:
        return 0
    for doc in documents:
        doc["date_archivage"] = datetime.now()
    db[collection + "_archives"].insert_many(documents)
    return db[collection].delete_many({"_id": {"$in": [d["_id"] for d in documents]}}).deleted_count


def archiver_evaluations_anciennes(db, mois=6):
    """Archive les évaluations de plus de <mois> mois."""
    limite = datetime.now() - timedelta(days=30 * mois)
    return archiver(db, "evaluations", {"date": {"$lt": limite}})


if __name__ == "__main__":
    # Petit test manuel
    from config import get_db
    db = get_db()
    print(len(chauffeurs_disponibles(db, "ZON-02")), "chauffeurs disponibles en ZON-02")
    print(len(chauffeurs_documents_expires(db)), "chauffeurs avec un document expiré")