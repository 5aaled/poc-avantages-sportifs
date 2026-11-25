
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_DIR = DATA_DIR / "output"
OUTBOX_DIR = DATA_DIR / "slack_outbox"
DB_PATH = DATA_DIR / "warehouse.db"
PARAMETERS_PATH = ROOT / "parametres.json"

RH_FILE = RAW_DIR / "Données+RH.xlsx"
SPORT_FILE = RAW_DIR / "Données+Sportive.xlsx"

REQUIRED_PARAMETERS = (
    "taux_prime",
    "seuil_activites",
    "jours_bien_etre",
    "distance_max_marche_km",
    "distance_max_velo_km",
    "jours_ouvrables_an",
    "score_geocodage_min",
    "adresse_entreprise",
    "seed_activites",
    "mois_historique",
)


def load_parameters() -> dict:
    if not PARAMETERS_PATH.exists():
        raise FileNotFoundError(f"Fichier de paramètres introuvable: {PARAMETERS_PATH}")
    params = json.loads(PARAMETERS_PATH.read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED_PARAMETERS if key not in params]
    if missing:
        raise ValueError(
            f"Paramètres manquants dans {PARAMETERS_PATH.name}: {', '.join(missing)}"
        )
    return params
