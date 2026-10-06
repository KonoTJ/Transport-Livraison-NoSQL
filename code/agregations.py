# agregations.py : index, agrégations et statistiques du Projet 4
from datetime import datetime
from pymongo import ASCENDING, DESCENDING, GEOSPHERE
from pymongo.errors import DuplicateKeyError, OperationFailure
from config import get_db


# ======================= INDEX ========================================
def creer_index(db):
    """Crée les index (sans danger si on relance : ils existent déjà)."""
    # Uniques : empêchent les doublons au niveau de la base
    for collection in ("zones", "chauffeurs", "clients", "courses"):
        db[collection].create_index("code", unique=True, name="uniq_code")
    db.chauffeurs.create_index("numero_permis", unique=True, name="uniq_permis")
    db.chauffeurs.create_index("vehicule.immatriculation", unique=True, name="uniq_immat")
    db.evaluations.create_index("course", unique=True, name="uniq_eval_course")   # relation 0..1
    db.paiements.create_index("course", unique=True, name="uniq_paiement_course")  # relation 0..1
    # Composés : pour les requêtes fréquentes
    db.courses.create_index([("ville", ASCENDING), ("statut", ASCENDING), ("date", DESCENDING)],
                            name="idx_ville_statut_date")
    db.chauffeurs.create_index([("zone", ASCENDING), ("statut", ASCENDING)],
                               name="idx_zone_statut")
    db.courses.create_index([("client", ASCENDING), ("date", DESCENDING)], name="idx_client_date")
    db.courses.create_index([("chauffeur", ASCENDING), ("date", DESCENDING)], name="idx_chauffeur_date")
    db.evaluations.create_index("chauffeur", name="idx_eval_chauffeur")
    # Géographique (bonus) : prépare la recherche des chauffeurs proches avec $near
    db.chauffeurs.create_index([("position", GEOSPHERE)], name="idx_position_2dsphere")
    print("Index créés :", [i["name"] for i in db.courses.list_indexes()])


def analyser(db, filtre, tri):
    """Affiche le plan d'exécution (explain) d'une recherche."""
    for _ in range(3):      # on répète : la 1re exécution est "à froid"
        plan = db.command("explain", {"find": "courses", "filter": filtre, "sort": tri},
                          verbosity="executionStats")
    stats = plan["executionStats"]
    gagnant = str(plan["queryPlanner"]["winningPlan"])
    methode = "IXSCAN (index utilisé)" if "IXSCAN" in gagnant \
        else "COLLSCAN (lecture de toute la collection)"
    print(f"  méthode : {methode}")
    print(f"  tri en mémoire : {'oui' if 'SORT' in gagnant else 'non'}")
    print(f"  documents examinés : {stats['totalDocsExamined']} | "
          f"clés d'index examinées : {stats['totalKeysExamined']} | "
          f"renvoyés : {stats['nReturned']} | temps : {stats['executionTimeMillis']} ms")


def comparer_avec_sans_index(db):
    """Montre l'effet de l'index composé (ville, statut, date) avec explain."""
    filtre = {"ville": "Douala", "statut": "terminee"}
    tri = {"date": -1}
    try:
        db.courses.drop_index("idx_ville_statut_date")
    except OperationFailure:
        pass                                    # l'index n'existait pas
    print("SANS index :")
    analyser(db, filtre, tri)
    db.courses.create_index([("ville", ASCENDING), ("statut", ASCENDING), ("date", DESCENDING)],
                            name="idx_ville_statut_date")
    print("AVEC index :")
    analyser(db, filtre, tri)


def demontrer_index_unique(db):
    """Montre qu'un doublon est refusé par un index unique."""
    evaluation = db.evaluations.find_one({}, {"_id": 0})
    try:
        db.evaluations.insert_one(dict(evaluation))
        print("❌ Doublon accepté (anormal)")
    except DuplicateKeyError:
        print("✅ Doublon refusé : une course n'a qu'une seule évaluation.")


# ======================= AGRÉGATIONS ==================================
def ca_par_ville_et_paiement(db):
    """1. Chiffre d'affaires par ville et par mode de paiement (courses terminées)."""
    return list(db.courses.aggregate([
        {"$match": {"statut": "terminee"}},
        {"$group": {"_id": {"ville": "$ville", "mode_paiement": "$mode_paiement"},
                    "chiffre_affaires": {"$sum": "$prix"},
                    "nb_courses": {"$sum": 1}}},
        {"$sort": {"_id.ville": 1, "chiffre_affaires": -1}},
    ]))


def top_chauffeurs(db, min_courses=20, limite=10):
    """2. Les chauffeurs les mieux notés ayant au moins 20 courses ($lookup + $unwind)."""
    return list(db.evaluations.aggregate([
        {"$group": {"_id": "$chauffeur",
                    "note_moyenne": {"$avg": "$note_chauffeur"},
                    "nb_evaluations": {"$sum": 1}}},
        {"$lookup": {"from": "chauffeurs", "localField": "_id",
                     "foreignField": "code", "as": "chauffeur"}},
        {"$unwind": "$chauffeur"},
        {"$match": {"chauffeur.nb_courses": {"$gte": min_courses}}},
        {"$project": {"_id": 0, "code": "$_id", "nom": "$chauffeur.nom",
                      "prenom": "$chauffeur.prenom", "nb_courses": "$chauffeur.nb_courses",
                      "nb_evaluations": 1,
                      "note_moyenne": {"$round": ["$note_moyenne", 2]}}},
        {"$sort": {"note_moyenne": -1, "nb_courses": -1}},
        {"$limit": limite},
    ]))


def heures_demandees(db, limite=24):
    """3. Heures de la journée les plus demandées."""
    return list(db.courses.aggregate([
        {"$group": {"_id": {"$hour": "$date"}, "nb_courses": {"$sum": 1}}},
        {"$sort": {"nb_courses": -1}},
        {"$limit": limite},
    ]))


def taux_annulation(db):
    """4. Taux d'annulation par ville et par type de course."""
    return list(db.courses.aggregate([
        {"$group": {"_id": {"ville": "$ville", "type": "$type"},
                    "total": {"$sum": 1},
                    "annulees": {"$sum": {"$cond": [{"$eq": ["$statut", "annulee"]}, 1, 0]}}}},
        {"$project": {"total": 1, "annulees": 1,
                      "taux_annulation_pct": {"$round": [
                          {"$multiply": [{"$divide": ["$annulees", "$total"]}, 100]}, 1]}}},
        {"$sort": {"taux_annulation_pct": -1}},
    ]))


def revenu_par_km(db):
    """5. Revenu moyen par kilomètre selon le type de véhicule."""
    return list(db.courses.aggregate([
        {"$match": {"statut": "terminee"}},
        {"$group": {"_id": "$type_vehicule",
                    "chiffre_affaires": {"$sum": "$prix"},
                    "km_total": {"$sum": "$distance_km"},
                    "nb_courses": {"$sum": 1}}},
        {"$project": {"chiffre_affaires": 1, "nb_courses": 1,
                      "km_total": {"$round": ["$km_total", 1]},
                      "revenu_par_km": {"$round": [
                          {"$divide": ["$chiffre_affaires", "$km_total"]}, 1]}}},
        {"$sort": {"revenu_par_km": -1}},
    ]))


def documents_expires_par_type(db):
    """6. Nombre de documents expirés par type ($unwind de la liste documents)."""
    return list(db.chauffeurs.aggregate([
        {"$unwind": "$documents"},
        {"$match": {"documents.date_expiration": {"$lt": datetime.now()}}},
        {"$group": {"_id": "$documents.type", "nb_expires": {"$sum": 1}}},
        {"$sort": {"nb_expires": -1}},
    ]))


def afficher(titre, resultats, maximum=10):
    print("\n" + "=" * 60 + f"\n{titre}\n" + "=" * 60)
    for ligne in resultats[:maximum]:
        print(ligne)


if __name__ == "__main__":
    db = get_db()
    creer_index(db)
    print("\n--- explain : effet de l'index ---")
    comparer_avec_sans_index(db)
    print("\n--- index unique ---")
    demontrer_index_unique(db)
    afficher("1. CA par ville et mode de paiement", ca_par_ville_et_paiement(db), 20)
    afficher("2. Top 10 chauffeurs (au moins 20 courses)", top_chauffeurs(db))
    afficher("3. Heures les plus demandées", heures_demandees(db, 5))
    afficher("4. Taux d'annulation par ville et type", taux_annulation(db), 8)
    afficher("5. Revenu moyen par km selon le véhicule", revenu_par_km(db))
    afficher("6. Documents expirés par type", documents_expires_par_type(db))