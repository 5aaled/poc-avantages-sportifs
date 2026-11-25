# Avantages sportifs — Sport Data Solution

To study the code file by file, start with [explanation/README.md](explanation/README.md). The pages there follow the import order and include the diagrams.

Pipeline du POC : lire les fichiers RH et sport, contrôler les trajets domicile-bureau, simuler douze mois de séances, calculer la prime et les journées bien-être, puis exposer le résultat pour Power BI.

La présentation orale et le rapport Power BI ne sont pas dans ce dépôt. Les fichiers de `data/output/` sont prêts à y être connectés.

## Par où commencer

Lis les fichiers dans cet ordre. Chaque fichier a un seul rôle. `src/pipeline.py` est le chef d'orchestre : il appelle les autres dans l'ordre des étapes.

| Ordre | Fichier | Ce qu'il faut y comprendre |
|---|---|---|
| 1 | `parametres.json` | Les chiffres métier : 5 %, 15 séances, 15 km, 25 km, 218 jours, adresse du bureau. Tout changement ici se répercute au prochain lancement. |
| 2 | `config.py` | Où sont les Excel, la base `data/warehouse.db`, les CSV, et le chargement de `parametres.json`. |
| 3 | `src/pipeline.py` | La fonction `executer`. C'est la carte du projet : extraction, distances, séances, contrôles, indicateurs, export. |
| 4 | `src/constantes.py` | Les 4 modes de déplacement du fichier RH, et lesquels sont soumis au contrôle de distance. |
| 5 | `src/extract.py` | Lecture des deux Excel et jointure sur `ID salarié`. Aucune donnée salarié n'est inventée ici. |
| 6 | `src/db.py` | Le schéma SQLite : une table par sujet. La base est un fichier local, sans serveur et sans Docker. |
| 7 | `src/eligibility.py` | Les règles. `evaluer_trajet` décide si un trajet est une anomalie. `calculer_eligibilite_salarie` décide la prime et les jours. `recalculer` réécrit les indicateurs. |
| 8 | `src/distances.py` | Distance domicile-bureau via la Base Adresse Nationale et OpenStreetMap. Le résultat est mis en cache dans `trajets`. |
| 9 | `src/http_client.py` | Envoi des requêtes HTTP. Détail technique, à lire après `distances.py`. |
| 10 | `src/activities.py` | Création des séances des 12 derniers mois, uniquement pour les salariés qui ont un sport. |
| 11 | `src/slack.py` | Transformation d'une séance en phrase, puis envoi webhook ou enregistrement local. |
| 12 | `src/quality.py` | La liste des contrôles : salaires, dates, distances, rattachement des séances. |
| 13 | `src/export.py` | Copie des tables vers `data/output/*.csv` pour Power BI. |
| 14 | `src/journal.py` et `src/monitor.py` | Le journal s'affiche dans le terminal à chaque étape. `monitor` relit `eligibilite` et affiche le coût courant. |
| 15 | `tests/test_regles.py` | Les mêmes règles, écrites comme des exemples chiffrés. Utile pour vérifier que tu as bien compris. |

`src/__main__.py` et `src/__init__.py` ne portent pas de logique. Ils permettent seulement `python -m src.pipeline`.

## Les étapes, dans l'ordre d'une exécution

Le point d'entrée est `python -m src.pipeline`, qui appelle `executer` dans `src/pipeline.py`.

### 1. Paramètres et base

`config.py` lit `parametres.json`. `src/db.py` crée le fichier `data/warehouse.db` et les quatre tables si elles n'existent pas : `employes`, `trajets`, `activites`, `eligibilite`. Chaque exécution reçoit un `run_id`, par exemple `20261019T213518-2f50`, affiché dans le terminal. Il n'est pas stocké.

### 2. Extraction

`src/extract.py` ouvre :

- `data/raw/Données+RH.xlsx` : identité, salaire, contrat, adresse, moyen de déplacement.
- `data/raw/Données+Sportive.xlsx` : le sport déclaré, ou vide.

Les deux fichiers ont les mêmes 161 identifiants. Le pipeline les joint, puis remplace le contenu de la table `employes`. Relancer le pipeline après une modification d'Excel recharge donc les salariés. Les Excel eux-mêmes ne sont jamais modifiés.

### 3. Distances domicile-bureau

`src/distances.py` prend l'adresse du salarié et l'adresse du bureau (`1362 Av. des Platanes, 34970 Lattes`). La Base Adresse Nationale trouve les coordonnées, OpenStreetMap calcule l'itinéraire. La colonne `source_calcul` vaut `openstreetmap`. Si l'itinéraire échoue, la distance reste vide et un trajet sportif devient une anomalie.

Le mode vient de `src/constantes.py`. Seuls `Marche/running` (15 km) et `Vélo/Trottinette/Autres` (25 km) sont contrôlés. La voiture et les transports ont quand même une distance, pour le rapport, mais elle ne retire aucun avantage.

`evaluer_trajet` dans `src/eligibility.py` écrit ensuite `est_anomalie` et `motif` :

- distance au-dessus du plafond ;
- adresse mal reconnue (score de géocodage sous `score_geocodage_min`, 0,5) ;
- distance impossible à calculer.

Une ligne déjà calculée pour la même adresse n'est pas rappelée. `--rebuild-distances` force le recalcul.

### 4. Séances simulées

Le fichier sport ne contient qu'un nom de sport, pas d'historique. `src/activities.py` invente les séances des 12 derniers mois pour les salariés qui ont un sport. Environ 80 % d'entre eux dépassent 15 séances, les autres restent en dessous, pour que la règle des jours bien-être ne soit pas automatique.

Chaque séance a : identifiant, salarié, début, fin, type, distance en mètres (vide pour l'escalade, le tennis, les sports collectifs et les sports de salle), commentaire, et le texte Slack. La graine `seed_activites` rend la simulation reproductible. Les salariés sans sport n'ont aucune séance.

`--rebuild-activities` efface les séances et les recrée.

### 5. Contrôles

`src/quality.py` vérifie les données avant de s'en servir pour l'argent :

- identifiants uniques, salaires strictement positifs, modes de déplacement reconnus ;
- chaque trajet sportif a une ligne de distance, aucune distance négative ;
- chaque séance pointe vers un salarié connu ;
- la fin est après le début, la durée reste sous 12 heures ;
- aucune distance de séance n'est négative.

Le résultat est affiché dans le terminal. Un échec n'efface pas les données : il fait terminer la commande avec un code d'erreur, pour que le problème reste visible.

### 6. Indicateurs

`recalculer` dans `src/eligibility.py` repart des salariés, des trajets et des séances, avec les paramètres du moment.

- Prime : salaire brut × `taux_prime` si le mode est sportif et que le trajet n'est pas une anomalie. Sinon 0 €.
- Jours bien-être : 5 jours si le nombre de séances de la période est au moins `seuil_activites`. Le coût d'une journée est salaire brut / `jours_ouvrables_an`. Les charges patronales ne sont pas ajoutées.
- Les deux avantages se cumulent. CDI et CDD sont traités de la même façon.

La table `eligibilite` est remplacée : elle contient toujours le dernier calcul. Le total de l'entreprise est affiché à la fin de la commande et par `python -m src.monitor`. Il n'est pas conservé d'une exécution à l'autre.

### 7. Export et journal

`src/export.py` écrit les CSV de `data/output/`. Chaque étape affiche aussi, dans le terminal, l'heure, le statut, les lignes lues et les lignes écrites. `python -m src.monitor` relit `eligibilite` et affiche le coût courant.

## Où va chaque information

| Table SQLite | CSV | Rôle |
|---|---|---|
| `employes` | `employes.csv` | Copie des Excel, une ligne par salarié |
| `trajets` | `trajets.csv` | Distance, score, anomalie, motif |
| `activites` | `activites.csv` | Séances des 12 derniers mois, avec le texte Slack |
| `eligibilite` | `eligibilite.csv` | Dernier calcul : prime, jours, coûts |

Pour Power BI, le fichier le plus simple est `data/output/indicateurs_salaries.csv` : une ligne par salarié, avec le trajet, l'éligibilité et les coûts. `activites.csv` sert au détail des séances.

## Règles métier

- Prime : 5 % du salaire annuel brut si le salarié déclare un trajet sportif et que la distance confirme la déclaration.
- Marche ou running : au plus 15 km.
- Vélo ou trottinette : au plus 25 km.
- Adresse mal reconnue : anomalie, prime non versée, motif explicite pour relecture humaine.
- Voiture et transports en commun : pas de prime.
- 5 journées bien-être à partir de 15 séances sur la période.
- Coût d'une journée : salaire brut annuel / 218. Les 218 jours sont l'hypothèse de jours ouvrés, modifiable dans `parametres.json`.

## Lancer le projet

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.pipeline
```

La première exécution interroge les API de géocodage et d'itinéraire. Elle dure quelques minutes. Les suivantes réutilisent les distances déjà stockées.

```bash
python -m src.monitor
pytest
```

## Slack

Chaque séance stocke sa phrase dans `message_slack`. Le pipeline ne poste pas ces phrases : un passage enverrait des milliers de messages. `envoyer_slack` sait envoyer une phrase si `SLACK_WEBHOOK_URL` est défini, et l'enregistrer dans `data/slack_outbox/messages.jsonl` sinon. Aucun fichier `.env` n'est lu.

## Rejouer les indicateurs

1. Noter le coût total avec `python -m src.monitor`.
2. Changer `taux_prime`, `seuil_activites` ou un plafond de distance dans `parametres.json`.
3. Relancer `python -m src.pipeline`.

Les séances simulées restent les mêmes. `eligibilite` contient le dernier calcul. Le calcul précédent est remplacé.

## Base locale

Il n'y a pas de Docker. SQLite est un fichier, `data/warehouse.db`, ouvert directement par Python. Aucun port n'est exposé. La base, les CSV et l'outbox Slack sont ignorés par Git. Le fichier n'a pas de mot de passe : sur cette machine, sa protection est de rester en local. Ne pas publier `data/raw/` sur un dépôt public, il contient les salaires et les adresses.

## Contrôles automatiques

`pytest` rejoue les règles sans appeler les API : 15 km inclus, 15,1 km refusé, 25 km pour le vélo, adresse mal reconnue, 14 séances sans jours bien-être, et une anomalie qui retire la prime sans retirer les jours.
