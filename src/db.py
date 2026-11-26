"""SQLite warehouse: schema and connection."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS employes (
    id_salarie INTEGER PRIMARY KEY,
    nom TEXT NOT NULL,
    prenom TEXT NOT NULL,
    date_naissance TEXT,
    bu TEXT,
    date_embauche TEXT,
    salaire_brut REAL NOT NULL,
    type_contrat TEXT,
    jours_cp INTEGER,
    adresse_domicile TEXT NOT NULL,
    moyen_deplacement TEXT NOT NULL,
    sport TEXT
);

CREATE TABLE IF NOT EXISTS trajets (
    id_salarie INTEGER PRIMARY KEY,
    adresse_domicile TEXT NOT NULL,
    adresse_entreprise TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    adresse_trouvee TEXT,
    score_geocodage REAL,
    distance_km REAL,
    duree_min REAL,
    mode_itineraire TEXT,
    source_calcul TEXT,
    seuil_km REAL,
    est_anomalie INTEGER NOT NULL,
    motif TEXT NOT NULL,
    calcule_le TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activites (
    id INTEGER PRIMARY KEY,
    id_salarie INTEGER NOT NULL,
    date_debut TEXT NOT NULL,
    date_fin TEXT NOT NULL,
    type_activite TEXT NOT NULL,
    distance_m REAL,
    commentaire TEXT,
    message_slack TEXT NOT NULL,
    cree_le TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activites_salarie ON activites (id_salarie);

CREATE TABLE IF NOT EXISTS eligibilite (
    id_salarie INTEGER PRIMARY KEY,
    eligible_prime INTEGER NOT NULL,
    motif_prime TEXT NOT NULL,
    montant_prime REAL NOT NULL,
    nb_activites INTEGER NOT NULL,
    eligible_bien_etre INTEGER NOT NULL,
    jours_bien_etre INTEGER NOT NULL,
    cout_jours_bien_etre REAL NOT NULL,
    cout_total REAL NOT NULL,
    taux_prime REAL NOT NULL,
    seuil_activites INTEGER NOT NULL,
    calcule_le TEXT NOT NULL
);
"""


def connect(path: Path | None = None) -> sqlite3.Connection:
    database = path or config.DB_PATH
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row   # allows us to access database query results using column names (e.g. row["name"]) instead of only numeric indexes (e.g. row[0]).
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()  # commit() permanently saves the changes made to the database by confirming the current transaction.


def horodatage(moment: datetime | None = None) -> str:
    moment = moment or datetime.now()
    return moment.replace(microsecond=0).isoformat(sep=" ")
