"""Consistency checks on the warehouse. Results are printed by the pipeline."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from src.constantes import MODES_ITINERAIRE, MODES_SPORTIFS


def controler_sources(conn: sqlite3.Connection, maintenant: datetime | None = None) -> list[dict]:
    maintenant = maintenant or datetime.now()
    employes = pd.read_sql_query("SELECT * FROM employes", conn)
    trajets = pd.read_sql_query("SELECT * FROM trajets", conn)
    activites = pd.read_sql_query("SELECT * FROM activites", conn)
    return [
        _identifiants_uniques(employes),
        _salaires_positifs(employes),
        _modes_connus(employes),
        _trajets_sportifs_presents(employes, trajets),
        _distances_trajets(trajets),
        _activites_rattachees(employes, activites),
        _distances_activites(activites),
        _dates_activites(activites, maintenant),
    ]


def controler_resultats(conn: sqlite3.Connection, params: dict) -> list[dict]:
    employes = pd.read_sql_query("SELECT id_salarie, salaire_brut FROM employes", conn)
    eligibilite = pd.read_sql_query("SELECT * FROM eligibilite", conn)
    controles = [_couverture_eligibilite(employes, eligibilite)]
    controles.append(_montants_coherents(employes, eligibilite, params))
    return controles


def a_des_echecs(controles: list[dict]) -> bool:
    return any(controle["statut"] == "echec" for controle in controles)


def _identifiants_uniques(employes: pd.DataFrame) -> dict:
    doubles = int(employes["id_salarie"].duplicated().sum())
    if doubles:
        return _resultat("identifiants_uniques", "echec", f"{doubles} identifiant(s) en double")
    return _resultat("identifiants_uniques", "ok", f"{len(employes)} salariés, identifiants uniques")


def _salaires_positifs(employes: pd.DataFrame) -> dict:
    invalides = employes[employes["salaire_brut"].isna() | (employes["salaire_brut"] <= 0)]
    if len(invalides):
        return _resultat("salaires_positifs", "echec", f"{len(invalides)} salaire(s) manquant(s) ou négatif(s)")
    return _resultat("salaires_positifs", "ok", "Tous les salaires bruts sont strictement positifs")


def _modes_connus(employes: pd.DataFrame) -> dict:
    inconnus = sorted(set(employes["moyen_deplacement"]) - set(MODES_ITINERAIRE))
    if inconnus:
        return _resultat(
            "modes_deplacement_connus",
            "avertissement",
            "Modes non prévus, traités comme non sportifs: " + ", ".join(inconnus),
        )
    return _resultat("modes_deplacement_connus", "ok", "Tous les modes de déplacement sont reconnus")


def _trajets_sportifs_presents(employes: pd.DataFrame, trajets: pd.DataFrame) -> dict:
    sportifs = employes[employes["moyen_deplacement"].isin(MODES_SPORTIFS)]
    if trajets.empty:
        manquants = sportifs
    else:
        manquants = sportifs[~sportifs["id_salarie"].isin(trajets["id_salarie"])]
    if len(manquants):
        return _resultat(
            "trajets_sportifs_presents",
            "echec",
            f"{len(manquants)} déplacement(s) sportif(s) sans distance calculée",
        )
    return _resultat(
        "trajets_sportifs_presents",
        "ok",
        f"{len(sportifs)} déplacement(s) sportif(s) ont une ligne de trajet",
    )


def _distances_trajets(trajets: pd.DataFrame) -> dict:
    if trajets.empty:
        return _resultat("distances_trajets_positives", "avertissement", "Aucun trajet enregistré")
    negatives = trajets[trajets["distance_km"] < 0]
    if len(negatives):
        return _resultat("distances_trajets_positives", "echec", f"{len(negatives)} distance(s) de trajet négative(s)")
    return _resultat("distances_trajets_positives", "ok", "Aucune distance de trajet négative")


def _activites_rattachees(employes: pd.DataFrame, activites: pd.DataFrame) -> dict:
    if activites.empty:
        return _resultat("activites_rattachees", "avertissement", "Aucune activité enregistrée")
    orphelines = activites[~activites["id_salarie"].isin(employes["id_salarie"])]
    if len(orphelines):
        return _resultat(
            "activites_rattachees",
            "echec",
            f"{len(orphelines)} activité(s) sans salarié correspondant",
        )
    return _resultat("activites_rattachees", "ok", f"{len(activites)} activités rattachées à un salarié")


def _distances_activites(activites: pd.DataFrame) -> dict:
    if activites.empty:
        return _resultat("distances_activites_positives", "ok", "Aucune activité à contrôler")
    negatives = activites[activites["distance_m"] < 0]
    if len(negatives):
        return _resultat(
            "distances_activites_positives",
            "echec",
            f"{len(negatives)} distance(s) d'activité négative(s)",
        )
    return _resultat("distances_activites_positives", "ok", "Aucune distance d'activité négative")


def _dates_activites(activites: pd.DataFrame, maintenant: datetime) -> dict:
    if activites.empty:
        return _resultat("dates_activites_valides", "ok", "Aucune activité à contrôler")
    debut = pd.to_datetime(activites["date_debut"])
    fin = pd.to_datetime(activites["date_fin"])
    limite = pd.Timestamp(maintenant) + pd.Timedelta(hours=1)
    invalides = activites[(fin <= debut) | ((fin - debut) > pd.Timedelta(hours=12)) | (fin > limite)]
    if len(invalides):
        return _resultat(
            "dates_activites_valides",
            "echec",
            f"{len(invalides)} activité(s) avec une date incohérente ou une durée supérieure à 12 h",
        )
    return _resultat("dates_activites_valides", "ok", "Dates de début, de fin et durées cohérentes")


def _couverture_eligibilite(employes: pd.DataFrame, eligibilite: pd.DataFrame) -> dict:
    if len(employes) != len(eligibilite):
        return _resultat(
            "couverture_eligibilite",
            "echec",
            f"{len(eligibilite)} lignes d'éligibilité pour {len(employes)} salariés",
        )
    return _resultat("couverture_eligibilite", "ok", "Chaque salarié a une ligne d'éligibilité")


def _montants_coherents(employes: pd.DataFrame, eligibilite: pd.DataFrame, params: dict) -> dict:
    if eligibilite.empty:
        return _resultat("montants_coherents", "echec", "Table d'éligibilité vide")
    taux = float(params["taux_prime"])
    jours = int(params["jours_bien_etre"])
    ouvrables = float(params["jours_ouvrables_an"])
    fusion = eligibilite.merge(employes, on="id_salarie", how="left")
    ecarts = []
    for ligne in fusion.to_dict(orient="records"):
        salaire = float(ligne["salaire_brut"])
        if ligne["eligible_prime"] == 1:
            attendu = round(salaire * taux, 2)
            if abs(ligne["montant_prime"] - attendu) > 0.02:
                ecarts.append(ligne["id_salarie"])
        elif ligne["montant_prime"] != 0:
            ecarts.append(ligne["id_salarie"])
        if ligne["eligible_bien_etre"] == 1:
            attendu_jours = round(salaire * jours / ouvrables, 2)
            if abs(ligne["cout_jours_bien_etre"] - attendu_jours) > 0.02:
                ecarts.append(ligne["id_salarie"])
        elif ligne["cout_jours_bien_etre"] != 0:
            ecarts.append(ligne["id_salarie"])
    if ecarts:
        apercu = ", ".join(str(identifiant) for identifiant in ecarts[:5])
        return _resultat("montants_coherents", "echec", f"{len(ecarts)} montant(s) incohérent(s), ex. {apercu}")
    return _resultat("montants_coherents", "ok", "Primes, jours bien-être et coûts totaux recalculés sans écart")


def _resultat(controle: str, statut: str, detail: str) -> dict:
    return {"controle": controle, "statut": statut, "detail": detail}
