# main.py : menu principal du Projet 4 (transport et livraison)
from pymongo.errors import PyMongoError
from config import get_db
import crud
import agregations
import generer_donnees


# ======================= SAISIES SÉCURISÉES ===========================
def saisir_texte(message):
    """Redemande tant que la saisie est vide."""
    while True:
        valeur = input(message).strip()
        if valeur:
            return valeur
        print("  ⚠ Saisie vide, recommencez.")


def saisir_nombre(message):
    """Redemande tant que la saisie n'est pas un nombre."""
    while True:
        try:
            return float(input(message).replace(",", "."))
        except ValueError:
            print("  ⚠ Entrez un nombre (exemple : 5.2).")


def saisir_point(libelle):
    """Demande une adresse et ses coordonnées, renvoie un dict départ/arrivée."""
    adresse = saisir_texte(f"  Adresse de {libelle} : ")
    lon = saisir_nombre(f"  Longitude de {libelle} (exemple 9.70) : ")
    lat = saisir_nombre(f"  Latitude de {libelle} (exemple 4.05) : ")
    crud.verifier_position(lon, lat)
    return {"adresse": adresse, "position": {"type": "Point", "coordinates": [lon, lat]}}


def afficher_liste(lignes, maximum=10):
    """Affiche au plus <maximum> lignes et indique s'il y en a d'autres."""
    if not lignes:
        print("  (aucun résultat)")
    for ligne in lignes[:maximum]:
        print(" ", ligne)
    if len(lignes) > maximum:
        print(f"  ... et {len(lignes) - maximum} autre(s) (total : {len(lignes)})")


# ======================= ACTIONS DU MENU ==============================
def menu_lire(db):
    print("\n  a) Chauffeurs disponibles d'une zone")
    print("  b) Courses d'un client")
    print("  c) Historique et évaluations d'un chauffeur")
    print("  d) Courses par statut")
    print("  e) Chauffeurs avec un document expiré")
    choix = input("  Votre choix : ").strip().lower()
    if choix == "a":
        afficher_liste(crud.chauffeurs_disponibles(db, saisir_texte("  Code zone (ex. ZON-01) : ")))
    elif choix == "b":
        afficher_liste(crud.courses_client(db, saisir_texte("  Code client (ex. CLI-0001) : ")), 5)
    elif choix == "c":
        courses, evals = crud.historique_chauffeur(db, saisir_texte("  Code chauffeur (ex. CHF-0001) : "))
        print(f"  {len(courses)} course(s), {len(evals)} évaluation(s)")
        afficher_liste(courses, 3)
        afficher_liste(evals, 3)
    elif choix == "d":
        statut = saisir_texte("  Statut (demandee, acceptee, en_cours, terminee, annulee) : ")
        afficher_liste(crud.courses_par_statut(db, statut), 5)
    elif choix == "e":
        afficher_liste(crud.chauffeurs_documents_expires(db), 5)
    else:
        print("  ⚠ Choix inconnu.")


def action_creer(db):
    code_client = saisir_texte("  Code client : ")
    code_chauffeur = saisir_texte("  Code chauffeur : ")
    type_course = saisir_texte("  Type (personne ou colis) : ")
    depart = saisir_point("départ")
    arrivee = saisir_point("arrivée")
    distance = saisir_nombre("  Distance en km : ")
    code = crud.creer_course(db, code_client, code_chauffeur, type_course, depart, arrivee, distance)
    print(f"  ✅ Course créée : {code}")
    print(" ", db.courses.find_one({"code": code}, {"_id": 0}))


def menu_modifier(db):
    print("\n  a) Mettre à jour la position d'un chauffeur")
    print("  b) Changer la disponibilité d'un chauffeur")
    print("  c) Faire avancer le statut d'une course")
    print("  d) Confirmer un paiement")
    choix = input("  Votre choix : ").strip().lower()
    if choix == "a":
        code = saisir_texte("  Code chauffeur : ")
        crud.maj_position(db, code, saisir_nombre("  Longitude : "), saisir_nombre("  Latitude : "))
        print("  ✅ Position mise à jour.")
    elif choix == "b":
        code = saisir_texte("  Code chauffeur : ")
        crud.changer_disponibilite(db, code, saisir_texte("  Statut (disponible, en_course, hors_ligne) : "))
        print("  ✅ Disponibilité mise à jour.")
    elif choix == "c":
        print("  ✅ Nouveau statut :", crud.avancer_statut_course(db, saisir_texte("  Code course : ")))
    elif choix == "d":
        crud.confirmer_paiement(db, saisir_texte("  Code course : "))
        print("  ✅ Paiement confirmé.")
    else:
        print("  ⚠ Choix inconnu.")


def menu_supprimer(db):
    print("\n  a) Supprimer les courses annulées")
    print("  b) Archiver les évaluations de plus de 6 mois")
    choix = input("  Votre choix : ").strip().lower()
    if choix in ("a", "b"):
        if input("  Cette opération modifie la base. Confirmer ? (o/n) ").strip().lower() != "o":
            print("  Annulé.")
            return
    if choix == "a":
        print(f"  ✅ {crud.supprimer_courses_annulees(db)} course(s) supprimée(s).")
    elif choix == "b":
        print(f"  ✅ {crud.archiver_evaluations_anciennes(db)} évaluation(s) archivée(s).")
    else:
        print("  ⚠ Choix inconnu.")


def menu_agregations(db):
    print("\n  1) CA par ville et mode de paiement   2) Top 10 chauffeurs")
    print("  3) Heures les plus demandées          4) Taux d'annulation")
    print("  5) Revenu moyen par km                6) Documents expirés par type")
    choix = input("  Votre choix : ").strip()
    actions = {
        "1": ("CA par ville et mode de paiement", agregations.ca_par_ville_et_paiement, 20),
        "2": ("Top 10 chauffeurs (au moins 20 courses)", agregations.top_chauffeurs, 10),
        "3": ("Heures les plus demandées", lambda d: agregations.heures_demandees(d, 5), 5),
        "4": ("Taux d'annulation par ville et type", agregations.taux_annulation, 8),
        "5": ("Revenu moyen par km selon le véhicule", agregations.revenu_par_km, 5),
        "6": ("Documents expirés par type", agregations.documents_expires_par_type, 5),
    }
    if choix in actions:
        titre, fonction, maximum = actions[choix]
        agregations.afficher(titre, fonction(db), maximum)
    else:
        print("  ⚠ Choix inconnu.")


def menu_index(db):
    print("\n  a) Créer les index")
    print("  b) Comparer avec et sans index (explain)")
    print("  c) Démontrer l'index unique (doublon refusé)")
    choix = input("  Votre choix : ").strip().lower()
    if choix == "a":
        agregations.creer_index(db)
    elif choix == "b":
        agregations.comparer_avec_sans_index(db)
    elif choix == "c":
        agregations.demontrer_index_unique(db)
    else:
        print("  ⚠ Choix inconnu.")


def action_generer(db):
    if input("  Cela efface et régénère toute la base. Confirmer ? (o/n) ").strip().lower() == "o":
        generer_donnees.tout_generer()
        agregations.creer_index(db)       # les index disparaissent avec les collections
    else:
        print("  Annulé.")


# ======================= MENU PRINCIPAL ===============================
MENU = """
============ TRANSPORT ET LIVRAISON ============
 1. Générer le jeu de données
 2. Lire
 3. Créer une course
 4. Modifier
 5. Supprimer / archiver
 6. Agrégations
 7. Index
 0. Quitter
"""

ACTIONS = {"1": action_generer, "2": menu_lire, "3": action_creer,
           "4": menu_modifier, "5": menu_supprimer, "6": menu_agregations, "7": menu_index}


def main():
    db = get_db()                         # s'arrête proprement si MongoDB est éteint
    print("Connecté à la base :", db.name)
    while True:
        print(MENU)
        choix = input("Votre choix : ").strip()
        if choix == "0":
            print("Au revoir.")
            break
        action = ACTIONS.get(choix)
        if not action:
            print("⚠ Choix inconnu, entrez un chiffre du menu.")
            continue
        try:
            action(db)
        except (ValueError, LookupError) as e:       # saisie invalide, introuvable
            print("  ⚠", e)
        except PyMongoError as e:                    # doublon, connexion perdue...
            print("  ⚠ Erreur de base de données :", e)


if __name__ == "__main__":
    main()