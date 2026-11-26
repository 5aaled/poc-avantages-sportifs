"""Read the two Excel sources and return one employee table."""

from __future__ import annotations

import pandas as pd

import config

COLONNES_RH = {
    "ID salarié": "id_salarie",
    "Nom": "nom",
    "Prénom": "prenom",
    "Date de naissance": "date_naissance",
    "BU": "bu",
    "Date d'embauche": "date_embauche",
    "Salaire brut": "salaire_brut",
    "Type de contrat": "type_contrat",
    "Nombre de jours de CP": "jours_cp",
    "Adresse du domicile": "adresse_domicile",
    "Moyen de déplacement": "moyen_deplacement",
}


def charger_sources() -> pd.DataFrame:
    if not config.RH_FILE.exists():
        raise FileNotFoundError(f"Fichier RH introuvable: {config.RH_FILE}")
    if not config.SPORT_FILE.exists():
        raise FileNotFoundError(f"Fichier sport introuvable: {config.SPORT_FILE}")

    rh = pd.read_excel(config.RH_FILE).rename(columns=COLONNES_RH)
    sport = pd.read_excel(config.SPORT_FILE).rename(
        columns={"ID salarié": "id_salarie", "Pratique d'un sport": "sport"}
    )
    manquantes = [col for col in COLONNES_RH.values() if col not in rh.columns]
    if manquantes or "sport" not in sport.columns:
        raise ValueError(f"Colonnes inattendues dans les fichiers sources: {manquantes}")

    if rh["id_salarie"].duplicated().any() or sport["id_salarie"].duplicated().any():
        raise ValueError("Identifiant salarié en double dans un fichier source.")

    ids_rh = set(rh["id_salarie"])
    ids_sport = set(sport["id_salarie"])
    if ids_rh != ids_sport:
        raise ValueError(
            "Les fichiers RH et sport n'ont pas les mêmes identifiants "
            f"(seulement RH: {len(ids_rh - ids_sport)}, seulement sport: {len(ids_sport - ids_rh)})."
        )

    employes = rh.merge(sport, on="id_salarie", how="left")
    employes["date_naissance"] = pd.to_datetime(employes["date_naissance"]).dt.date
    employes["date_embauche"] = pd.to_datetime(employes["date_embauche"]).dt.date
    employes["sport"] = employes["sport"].where(employes["sport"].notna(), None)  # .where(condition, other)  # This line replaces missing values (NaN) in the sport column with Python's None, which represents SQL NULL when inserting data into SQLite."
    employes["salaire_brut"] = employes["salaire_brut"].astype(float)
    return employes.sort_values("id_salarie").reset_index(drop=True)
