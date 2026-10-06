# Projet 4 : Plateforme de transport et de livraison (MongoDB + Python)

Auteur : Kono Tchoumba Jordan Julien Claude, Groupe 04, SDIA-4
Matière : Big Data et NoSQL. Enseignant : M. Fotso T. Valdez W.

## 1. Prérequis
- Python 3.8 ou plus récent
- MongoDB Community Server démarré sur `localhost:27017`
- MongoDB Database Tools (`mongoimport`) si vous importez les exports

## 2. Installation
```
pip install -r requirements.txt
```

## 3. Configuration
Tout se règle dans `config.py` : `MONGO_URI` (adresse de connexion) et `NOM_BASE` (`transport_kono`).

## 4. Obtenir les données (deux méthodes)

**Méthode A : régénérer (recommandée)**, avec le jeu de données reproductible (`seed = 42`) :
```
python generer_donnees.py
python agregations.py
```
Le premier script crée 5 zones, 100 chauffeurs, 300 clients, 1200 courses,
environ 1000 paiements et 900 évaluations. Le second crée les index.

**Méthode B : importer les exports JSON** depuis le dossier `exports/json` :
```
mongoimport --db=transport_kono --collection=zones --jsonArray --file=exports/json/zones.json
```
(à répéter pour chauffeurs, clients, courses, evaluations, paiements), puis :
```
python agregations.py
```
car l'import ne recrée pas les index.

## 5. Lancer l'application
```
python main.py
```
Le menu propose : générer les données, lire, créer une course, modifier,
supprimer/archiver, agrégations, index.

## 6. Contenu des fichiers
| Fichier | Rôle |
|---|---|
| `config.py` | connexion et nom de la base (seul fichier à modifier) |
| `generer_donnees.py` | génération des données |
| `crud.py` | opérations Créer / Lire / Modifier / Supprimer |
| `agregations.py` | index, explain et 6 agrégations |
| `main.py` | menu principal |

## 7. Modélisation (résumé)
- Imbriqué : véhicule, documents, position (chauffeurs) ; adresses favorites (clients) ; départ et arrivée (courses) ; majoration de pointe (zones).
- Référencé par code : zone (chauffeurs, courses), client, chauffeur (courses), course (évaluations, paiements).
- Copié dans la course : `ville`, `type_vehicule`, `prix`, `mode_paiement`.

## 8. Notes
- Supprimer les courses annulées et archiver les évaluations (menu 5) modifie la base.
  L'option 1 du menu régénère tout.
- Les transactions multi-documents exigent un replica set ; en local simple, la
  cohérence entre courses, chauffeurs et paiements repose sur les filtres du code.