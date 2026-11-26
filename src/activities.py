"""Simulated sessions for the last 12 months."""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import pandas as pd

from src.eligibility import debut_fenetre
from src.slack import formater_message


SPORTS_DISTANCE = [
    "Runing",
    "Randonnée",
    "Natation",
    "Triathlon",
]
SPORTS_SANS_DISTANCE = [
    "Tennis",
    "Tennis de table",
    "Football",
    "Rugby",
    "Basketball",
    "Badminton",
    "Judo",
    "Boxe",
    "Escalade",
    "Voile",
    "Équitation",
]
COMMENTAIRES = ["Sortie facile", "Séance du soir", "Reprise du sport :)"]


def profil_pour(sport: str | None) -> dict | None:
    if sport is None:
        return None
    if sport in SPORTS_DISTANCE:
        return {"type": sport, "avec_distance": True}
    if sport in SPORTS_SANS_DISTANCE:
        return {"type": sport, "avec_distance": False}
    return {"type": str(sport), "avec_distance": False}


def generer_activites( employes: pd.DataFrame,params: dict,maintenant: datetime | None = None,) -> pd.DataFrame:

    maintenant = maintenant or datetime.now().replace(microsecond=0)
    seed = int(params["seed_activites"])
    lignes = []
    for employe in employes.to_dict(orient="records"):
        profil = profil_pour(employe.get("sport"))
        if profil is None:  # in this case i will not create an activity for this employ because he doesnt have sport
            continue
        generateur = random.Random(f"{seed}-{int(employe['id_salarie'])}")  # so by each run for the same employ it gives me same random result
        lignes.extend(_seances_salarie(employe, profil, params, maintenant, generateur))
    colonnes = [
        "id_salarie",
        "date_debut",
        "date_fin",
        "type_activite",
        "distance_m",
        "commentaire",
        "message_slack",
        "cree_le",
    ]
    if not lignes:
        return pd.DataFrame(columns=colonnes)
    return pd.DataFrame(lignes).sort_values(["date_debut", "id_salarie"]).reset_index(drop=True)


#generate a list of simulated sports sessions for one employee, over a defined historical period.
def _seances_salarie(employe, profil, params, maintenant, generateur) -> list[dict]:

    embauche = _comme_datetime(employe.get("date_embauche")) # convert the date into datetime
    debut_periode = max(debut_fenetre(maintenant, int(params["mois_historique"])), embauche)
    if debut_periode >= maintenant:
        return []
    jours = max((maintenant - debut_periode).days, 1)
    nombre = generateur.randint(20, 60) if generateur.random() < 0.80 else generateur.randint(5, 14)
    nombre = min(nombre, max(jours // 3, 1))  # this to determine how many session we want to create for each employee
  # nombre is the total number of sessions to create for that person during the window: the random target of 20 to 60 or 5 to 14, reduced when the days since hire cannot hold that many at one session every three days.
    jours_pris = set()
    seances = []
    for _ in range(nombre):
        distance, minutes = _distance_et_duree(generateur, profil)
        debut = _tirer_debut(generateur, debut_periode, maintenant, minutes, jours_pris)
        if debut is None:
            continue
        jours_pris.add(debut.date())
        commentaire = generateur.choice(COMMENTAIRES) if generateur.random() < 0.40 else None  #  40% of sessions get a comment, and the other 60% stay empty.
        seances.append(
            _ligne(
                employe,
                profil,
                debut,
                debut + timedelta(minutes=minutes),
                distance,
                commentaire,
                maintenant,
            )
        )
    return seances


def _ligne(employe, profil, debut, fin, distance, commentaire, cree_le) -> dict:
    return {
        "id_salarie": int(employe["id_salarie"]),
        "date_debut": debut,
        "date_fin": fin,
        "type_activite": profil["type"],
        "distance_m": distance,
        "commentaire": commentaire,
        "message_slack": formater_message(
            employe["prenom"],
            employe["nom"],
            profil["type"],
            distance,
            debut,
            fin,
            commentaire,
        ),
        "cree_le": cree_le,
    }

# _distance_et_duree invents two facts for one session: how far it was, and how long it lasted. The caller unpacks them as distance, minutes.
def _distance_et_duree(generateur: random.Random, profil: dict) -> tuple[float | None, int]:
    if not profil["avec_distance"]:
        return None, generateur.randint(45, 90)
    metres = generateur.randint(3, 15) * 1000
    return float(metres), max(round(metres / 1000 * 6), 10)


def _tirer_debut(generateur, debut, fin, minutes, jours_pris):    # jours_pris stops one employee from getting two sessions on the same calendar day.
    dernier = fin - timedelta(minutes=minutes)
    if dernier <= debut:
        return None
    nb_jours = max((dernier.date() - debut.date()).days, 0)
    for _ in range(40):
        jour = debut.date() + timedelta(days=generateur.randint(0, nb_jours))
        if jour in jours_pris:
            continue
        candidat = datetime(
            jour.year,
            jour.month,
            jour.day,
            generateur.choice([7, 8, 12, 18, 19]),
            generateur.choice([0, 15, 30, 45]),
        )
        if debut <= candidat <= dernier:
            return candidat
    return None


def _comme_datetime(valeur) -> datetime:
    return datetime.combine(valeur, datetime.min.time())
