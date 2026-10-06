# config.py : le seul fichier à modifier pour changer de base
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

MONGO_URI = "mongodb://localhost:27017/"
NOM_BASE = "transport_kono"

def get_db():
    """Ouvre la connexion et renvoie la base, ou arrête le programme proprement."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        print("Connexion réussie")
    except ServerSelectionTimeoutError:
        raise SystemExit("Impossible de joindre MongoDB : vérifiez qu'il est démarré.")
    return client[NOM_BASE]

from config import get_db
db = get_db()
print(db.name)   # doit afficher transport_kono