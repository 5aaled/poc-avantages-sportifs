"""Prime and wellness-day rules. Indicators are recomputed on every run."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from src.constantes import MODES_SPORTIFS, SEUIL_PARAM
from src.db import horodatage


def debut_fenetre(maintenant: datetime, mois: int) -> datetime:
    """Start of the history window, `mois` months before `maintenant`."""
    mois = int(mois)
    annee = maintenant.year
    mois_cible = maintenant.month - mois
    while mois_cible <= 0:
        mois_cible += 12
        annee -= 1
    dernier_jour = [31, 29 if _bissextile(annee) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][
        mois_cible - 1
    ]
    jour = min(maintenant.day, dernier_jour)
    return maintenant.replace(year=annee, month=mois_cible, day=jour, microsecond=0)


def evaluer_trajet(mode: str, distance_km: float | None, score: float | None, params: dict) -> dict:
    """Flag a commute declaration that the distance rule cannot support."""
    if mode not in SEUIL_PARAM:
        return {
            "est_anomalie": 0,
            "seuil_km": None,
            "motif": "Déplacement non sportif, le contrôle de distance ne s'applique pas",
        }

    seuil = float(params[SEUIL_PARAM[mode]])   #max distance
    if distance_km is None:
        return {
            "est_anomalie": 1,
            "seuil_km": seuil,
            "motif": "Distance domicile-bureau introuvable, déclaration non vérifiée",
        }
    if distance_km < 0:
        return {
            "est_anomalie": 1,
            "seuil_km": seuil,
            "motif": "Distance négative",
        }
    if not _geocodage_fiable(score, params):
        return {
            "est_anomalie": 1,
            "seuil_km": seuil,
            "motif": (
                f"Adresse mal reconnue (score {_fr(score, 2)}), "
                f"distance de {_fr(distance_km, 1)} km à vérifier"
            ),
        }
    if distance_km > seuil:
        return {
            "est_anomalie": 1,
            "seuil_km": seuil,
            "motif": (
                f"Distance de {_fr(distance_km, 1)} km au-dessus du maximum "
                f"de {_fr(seuil, 0)} km pour ce mode"
            ),
        }
    return {
        "est_anomalie": 0,
        "seuil_km": seuil,
        "motif": f"Distance de {_fr(distance_km, 1)} km, dans la limite de {_fr(seuil, 0)} km",
    }


def calculer_eligibilite_salarie(
    salaire: float, mode: str, est_anomalie: int , motif_trajet: str,nb_activites: int,
params: dict,
) -> dict:
    taux = float(params["taux_prime"])
    seuil = int(params["seuil_activites"])
    jours = int(params["jours_bien_etre"])
    ouvrables = float(params["jours_ouvrables_an"])

    if mode in MODES_SPORTIFS and not est_anomalie:
        eligible_prime = 1
        motif_prime = motif_trajet
        montant_prime = round(float(salaire) * taux, 2)
    elif mode in MODES_SPORTIFS:
        eligible_prime = 0
        motif_prime = motif_trajet
        montant_prime = 0.0
    else:
        eligible_prime = 0
        motif_prime = "Moyen de déplacement non sportif"
        montant_prime = 0.0

    eligible_bien_etre = int(nb_activites >= seuil)
    jours_bien_etre = jours if eligible_bien_etre else 0
    cout_jours = round(float(salaire) * jours_bien_etre / ouvrables, 2) if eligible_bien_etre else 0.0
    return {
        "eligible_prime": eligible_prime,
        "motif_prime": motif_prime,
        "montant_prime": montant_prime,
        "nb_activites": int(nb_activites),
        "eligible_bien_etre": eligible_bien_etre,
        "jours_bien_etre": jours_bien_etre,
        "cout_jours_bien_etre": cout_jours,
        "cout_total": round(montant_prime + cout_jours, 2),
        "taux_prime": taux,
        "seuil_activites": seuil,
    }


def recalculer(
    conn: sqlite3.Connection,
    params: dict,
    maintenant: datetime | None = None,
) -> dict:
    """Replace eligibilite with the current decision and return the company totals."""
    maintenant = maintenant or datetime.now().replace(microsecond=0)
    moment = horodatage(maintenant)
    lignes = _lignes_eligibilite(conn, params, maintenant, moment)

    conn.execute("DELETE FROM eligibilite")
    if lignes:
        colonnes = [
            "id_salarie",
            "eligible_prime",
            "motif_prime",
            "montant_prime",
            "nb_activites",
            "eligible_bien_etre",
            "jours_bien_etre",
            "cout_jours_bien_etre",
            "cout_total",
            "taux_prime",
            "seuil_activites",
            "calcule_le",
        ]
        conn.executemany(
            f"INSERT INTO eligibilite ({', '.join(colonnes)}) VALUES ({', '.join('?' for column in colonnes)})",
            [tuple(ligne[col] for col in colonnes) for ligne in lignes],
        )

    nb_anomalies = conn.execute("SELECT COUNT(*) FROM trajets WHERE est_anomalie = 1").fetchone()[0]
    nb_activites = conn.execute("SELECT COUNT(*) FROM activites").fetchone()[0]
    totaux = {
        "calcule_le": moment,
        "taux_prime": float(params["taux_prime"]),
        "seuil_activites": int(params["seuil_activites"]),
        "nb_salaries": len(lignes),
        "nb_eligible_prime": sum(ligne["eligible_prime"] for ligne in lignes),
        "nb_eligible_bien_etre": sum(ligne["eligible_bien_etre"] for ligne in lignes),
        "nb_anomalies_trajet": int(nb_anomalies),
        "nb_activites": int(nb_activites),
        "cout_primes": round(sum(ligne["montant_prime"] for ligne in lignes), 2),
        "cout_jours_bien_etre": round(sum(ligne["cout_jours_bien_etre"] for ligne in lignes), 2),
        "cout_total": round(sum(ligne["cout_total"] for ligne in lignes), 2),
    }
    conn.commit()   # It confirms the transaction and saves those changes to the database.
    return totaux


def _lignes_eligibilite(conn, params, maintenant, moment) -> list[dict]:
    fenetre = horodatage(debut_fenetre(maintenant, int(params["mois_historique"])))
    comptes = dict(
        conn.execute(
            """
            SELECT id_salarie, COUNT(*)
            FROM activites
            WHERE date_debut >= ?
            GROUP BY id_salarie
            """,
            (fenetre,),
        ).fetchall()
    )
    trajets = {
        row["id_salarie"]: row  for row in conn.execute("SELECT id_salarie, est_anomalie, motif FROM trajets")
    }
    lignes = []
    for employe in conn.execute("SELECT id_salarie, salaire_brut, moyen_deplacement FROM employes"):
        trajet = trajets.get(employe["id_salarie"])
        if trajet is None and employe["moyen_deplacement"] in MODES_SPORTIFS:
            est_anomalie = 1
            motif = "Distance domicile-bureau introuvable, déclaration non vérifiée"
        elif trajet is None:
            est_anomalie = 0
            motif = "Déplacement non sportif, le contrôle de distance ne s'applique pas"
        else:
            est_anomalie = int(trajet["est_anomalie"])
            motif = trajet["motif"]
        calcule = calculer_eligibilite_salarie(
            employe["salaire_brut"],
            employe["moyen_deplacement"],
            est_anomalie,
            motif,
            int(comptes.get(employe["id_salarie"], 0)),
            params,
        )
        calcule["id_salarie"] = int(employe["id_salarie"])
        calcule["calcule_le"] = moment
        lignes.append(calcule)
    return lignes


def _geocodage_fiable(score: float | None, params: dict) -> bool:
    if score is None:
        return True
    return float(score) >= float(params["score_geocodage_min"])


def _fr(valeur: float, decimales: int) -> str:
    return f"{float(valeur):.{decimales}f}".replace(".", ",")


def _bissextile(annee: int) -> bool : # Returns True if the given year is a leap year (366 days); otherwise, returns False (365 days).
    return annee % 400 == 0 or (annee % 4 == 0 and annee % 100 != 0)
