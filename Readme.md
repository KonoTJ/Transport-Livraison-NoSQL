# 🚗 Plateforme de transport et de livraison — MongoDB & Python

Projet NoSQL réalisé dans le cadre de l'évaluation finale du cours *Du SQL au NoSQL*
(bases de données, Big Data, MongoDB et Python) — SDIA-4, ENSPD.

Une application de type VTC/livraison (motos, voitures, camionnettes) mettant en
relation clients et chauffeurs dans plusieurs villes, avec tarification par zone,
paiements mobile money, et suivi des courses de bout en bout.

## Ce que couvre le projet

- **Modélisation NoSQL** — 6 collections (chauffeurs, clients, zones, courses,
  évaluations, paiements), avec un choix justifié entre documents imbriqués et
  références selon le volume et le cycle de vie de chaque donnée.
- **CRUD complet en Python** (pymongo) — création de course avec calcul de prix
  dynamique (zone + heures de pointe), lecture filtrée, mise à jour du cycle de
  vie d'une course, archivage plutôt que suppression.
- **Agrégations et index** — 6 pipelines d'agrégation (dont `$lookup` et
  `$unwind`), index uniques et composés, effet mesuré avec `explain`.
- **Génération de données réaliste et reproductible** — jeu de données généré
  avec `random.seed(42)` pour que les résultats soient toujours vérifiables.
- **Gestion des erreurs** — saisies invalides, documents introuvables, doublons,
  connexion MongoDB indisponible.

## Structure du dépôt

```
code/
├── config.py            # connexion MongoDB (seul fichier à modifier)
├── generer_donnees.py   # génération du jeu de données
├── crud.py               # opérations Créer / Lire / Modifier / Supprimer
├── agregations.py        # pipelines d'agrégation, index, explain
├── main.py               # menu principal
└── README.md             # installation et lancement détaillés

exports/
├── json/                 # export complet de chaque collection
└── csv/                  # export plat des collections principales

captures/                 # captures d'écran des résultats réels
rapport_Groupe04_Kono.pptx
video_demo.mp4
```

## Lancer le projet

```bash
pip install -r code/requirements.txt
python code/generer_donnees.py   # génère ~1 200 courses, 100 chauffeurs...
python code/agregations.py       # crée les index
python code/main.py              # menu interactif
```

Nécessite une instance MongoDB locale (ou Atlas) et son adresse dans `config.py`.
Détails complets dans [`code/README.md`](code/README.md).

## Stack

**MongoDB** · **Python** (pymongo) · agrégations `$lookup` / `$unwind` ·
index composés et géospatiaux (`2dsphere`)

---

*Projet individuel — Groupe 04, SDIA-4. Encadrant : M. FOTSO T. Valdez W.*