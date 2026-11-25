
from __future__ import annotations

import sqlite3

import pandas as pd

import config

TABLES = (
    "employes",
    "trajets",
    "activites",
    "eligibilite",
)

REQUETE_INDICATEURS = """
SELECT
    e.id_salarie,
    e.nom,
    e.prenom,
    e.bu,
    e.type_contrat,
    e.salaire_brut,
    e.moyen_deplacement,
    e.sport,
    e.date_embauche,
    t.distance_km,
    t.duree_min,
    t.est_anomalie,
    t.motif AS motif_trajet,
    t.score_geocodage,
    t.source_calcul,
    el.eligible_prime,
    el.motif_prime,
    el.montant_prime,
    el.nb_activites,
    el.eligible_bien_etre,
    el.jours_bien_etre,
    el.cout_jours_bien_etre,
    el.cout_total,
    el.taux_prime,
    el.seuil_activites
FROM employes e
LEFT JOIN trajets t ON t.id_salarie = e.id_salarie
LEFT JOIN eligibilite el ON el.id_salarie = e.id_salarie
ORDER BY e.id_salarie
"""


def exporter(conn: sqlite3.Connection) -> None:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        frame = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        frame.to_csv(config.OUTPUT_DIR / f"{table}.csv", index=False, encoding="utf-8-sig")
    indicateurs = pd.read_sql_query(REQUETE_INDICATEURS, conn)
    indicateurs.to_csv(config.OUTPUT_DIR / "indicateurs_salaries.csv", index=False, encoding="utf-8-sig")
