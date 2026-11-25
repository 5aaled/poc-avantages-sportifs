"""Slack text for one session, and delivery through a webhook or a local outbox."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime

import config
from src.db import horodatage
from src.http_client import post_json


def formater_message(
    prenom: str,
    nom: str,
    type_activite: str,
    distance_m: float | None,
    date_debut: datetime | str,
    date_fin: datetime | str,
    commentaire: str | None,
) -> str:
    debut = _comme_datetime(date_debut)
    fin = _comme_datetime(date_fin)
    minutes = max(1, round((fin - debut).total_seconds() / 60))  # Subtracting two datetime objects gives you a timedelta object. The total_seconds() method belongs to that resulting object, not directly to datetime.
    qui = f"{prenom} {nom}".strip()
    distance = _distance(distance_m)

    if type_activite == "Runing" and distance:
        return (
            f"Bravo {qui} ! Tu viens de courir {_km(distance, 1)} km en {minutes} min !"
            " Quelle énergie ! 🔥🏅"
        )
    if type_activite == "Randonnée" and distance:
        precision = 0 if distance >= 10000 else 1
        citation = f' ("{commentaire}")' if commentaire else ""
        return (
            f"Magnifique {qui} ! Une randonnée de {_km(distance, precision)} km terminée"
            f" et un nouveau spot à découvrir ! 🌄{citation} 🏕"
        )
    if type_activite == "Natation" and distance:
        return f"Bravo {qui} ! {int(round(distance))} m nagés en {minutes} min ! 🏊"
    if type_activite == "Escalade":
        return f"Bravo {qui} ! Séance d'escalade terminée en {minutes} min ! 🧗"
    if distance:
        return f"Bravo {qui} ! {type_activite} terminé : {_km(distance, 1)} km en {minutes} min !"
    texte = f"Bravo {qui} ! Séance de {type_activite.lower()} terminée en {minutes} min !"
    if commentaire:
        texte += f" ({commentaire})"
    return texte


def envoyer_slack(message: str, id_salarie: int | None = None) -> str:
    """Send the message, or keep it locally when no webhook is configured.

    Returns envoye, simule, or erreur.
    """
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    statut = "simule"
    detail = ""
    if webhook:
        try:
            code, body = post_json(webhook, {"text": message})
            statut = "envoye" if code == 200 else "erreur"
            detail = body[:200]
        except Exception as exc:  # noqa: BLE001 - delivery must not lose the activity
            statut = "erreur"
            detail = str(exc)[:200]

    config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    ligne = {
        "date": horodatage(),
        "statut": statut,
        "id_salarie": id_salarie,
        "message": message,
        "detail": detail,
    }
    with (config.OUTBOX_DIR / "messages.jsonl").open("a", encoding="utf-8") as fichier:
        fichier.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    return statut


def _km(metres: float, decimales: int) -> str:
    return f"{metres / 1000:.{decimales}f}".replace(".", ",")


def _distance(valeur) -> float | None:
    if valeur is None:
        return None
    try:
        if math.isnan(float(valeur)):   # math is biult in module in python isnan is a function that check wether the input is number or not
            return None
    except (TypeError, ValueError):
        return None
    return float(valeur)


def _comme_datetime(valeur: datetime | str) -> datetime:
    if isinstance(valeur, datetime):
        return valeur
    return datetime.fromisoformat(str(valeur))
