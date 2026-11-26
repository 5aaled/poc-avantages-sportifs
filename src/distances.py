"""Home-to-office distance through the French address API and OpenStreetMap."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import pandas as pd

from src.constantes import MODES_ITINERAIRE, SEUIL_PARAM
from src.db import horodatage
from src.eligibility import evaluer_trajet
from src.http_client import construire_url, get_json

BAN_URL = "https://api-adresse.data.gouv.fr/search/"
OSRM = {
    "walking": ("https://routing.openstreetmap.de/routed-foot/route/v1/foot/", "walking"),
    "bicycling": ("https://routing.openstreetmap.de/routed-bike/route/v1/bike/", "bicycling"),
    "driving": ("https://router.project-osrm.org/route/v1/driving/", "driving"),
    "transit": ("https://router.project-osrm.org/route/v1/driving/", "transit_approx_voiture"),
}

# the main function that run for all employess
def calculer_trajets(
    conn: sqlite3.Connection, employes: pd.DataFrame,params: dict,reconstruire: bool = False, maintenant: datetime | None = None,) -> tuple[int, int]:

    maintenant = maintenant or datetime.now().replace(microsecond=0)
    adresse_bureau = params["adresse_entreprise"]
    if reconstruire:
        conn.execute("DELETE FROM trajets")
        conn.commit()

    bureau = _geocoder_bureau(adresse_bureau)
    connus = {
        row["id_salarie"]: row["adresse_domicile"]  for row in conn.execute("SELECT id_salarie, adresse_domicile FROM trajets")
    }
    a_calculer = []
    for employe in employes.to_dict(orient="records"):
        adresse = str(employe["adresse_domicile"])
        if connus.get(int(employe["id_salarie"])) == adresse:
            continue
        a_calculer.append(employe)

    deja = len(employes) - len(a_calculer)
    for index, employe in enumerate(a_calculer, start=1):
        if index == 1 or index % 20 == 0 or index == len(a_calculer):
            print(f"  distance {index}/{len(a_calculer)}", flush=True)
        ligne = _trajet_salarie(employe, adresse_bureau, bureau, params, maintenant)
        _ecrire_trajet(conn, ligne)
    return len(a_calculer), deja

# ,calcute for only one employee
def _trajet_salarie(employe, adresse_bureau, bureau, params, maintenant) -> dict:
    mode = str(employe["moyen_deplacement"])
    profil = MODES_ITINERAIRE.get(mode, "driving")  # here i exctract moyen de deplacement groupé that i will insert to calculte the distance in the function distance
    adresse = str(employe["adresse_domicile"])
    try:
        mesure = _distance(adresse, bureau, profil)
    except Exception as exc:
        mesure = {
            "latitude": None,
            "longitude": None,
            "adresse_trouvee": None,
            "score_geocodage": None,
            "distance_km": None,
            "duree_min": None,
            "mode_itineraire": profil,
            "source_calcul": "openstreetmap",
            "erreur": str(exc)[:180],
        }

    verdict = evaluer_trajet(mode, mesure.get("distance_km"), mesure.get("score_geocodage"), params)
    if mesure.get("erreur") and mesure.get("distance_km") is None and mode in SEUIL_PARAM:
        verdict = {
            "est_anomalie": 1,
            "seuil_km": verdict["seuil_km"],
            "motif": f"Calcul de distance en échec ({mesure['erreur']})",
        }
    return {
        "id_salarie": int(employe["id_salarie"]),
        "adresse_domicile": adresse,
        "adresse_entreprise": adresse_bureau,
        "latitude": mesure.get("latitude"),
        "longitude": mesure.get("longitude"),
        "adresse_trouvee": mesure.get("adresse_trouvee"),
        "score_geocodage": mesure.get("score_geocodage"),
        "distance_km": _arrondi(mesure.get("distance_km"), 3),
        "duree_min": _arrondi(mesure.get("duree_min"), 1),
        "mode_itineraire": mesure.get("mode_itineraire") or profil,
        "source_calcul": mesure.get("source_calcul") or "openstreetmap",
        "seuil_km": verdict["seuil_km"],
        "est_anomalie": verdict["est_anomalie"],
        "motif": verdict["motif"],
        "calcule_le": horodatage(maintenant),
    }


def _distance(adresse: str, bureau: dict, profil: str) -> dict:
    lieu = _geocode_ban(adresse)
    base, mode_label = OSRM[profil]
    distance_km, duree_min = _route_osrm(
        base, lieu["longitude"], lieu["latitude"], bureau["longitude"], bureau["latitude"]
    )
    return {
        "latitude": lieu["latitude"],
        "longitude": lieu["longitude"],
        "adresse_trouvee": lieu["adresse_trouvee"],
        "score_geocodage": lieu["score_geocodage"],
        "distance_km": distance_km,
        "duree_min": duree_min,
        "mode_itineraire": mode_label,
        "source_calcul": "openstreetmap",
    }


def _geocode_ban(adresse: str) -> dict:
    payload = get_json(construire_url(BAN_URL, {"q": f"{adresse}, France", "limit": 1}))
    features = payload.get("features") or []
    if not features:
        raise RuntimeError(f"adresse introuvable: {adresse}")
    proprietes = features[0]["properties"]
    longitude, latitude = features[0]["geometry"]["coordinates"]
    return {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "adresse_trouvee": proprietes.get("label"),
        "score_geocodage": float(proprietes.get("score") or 0),
    }


def _route_osrm(base: str, lon1: float, lat1: float, lon2: float, lat2: float) -> tuple[float, float]:
    url = f"{base}{lon1},{lat1};{lon2},{lat2}?overview=false"
    payload = get_json(url)
    if payload.get("code") != "Ok":
        raise RuntimeError(payload.get("message") or payload.get("code") or "itinéraire introuvable")
    route = payload["routes"][0]
    return route["distance"] / 1000, route["duration"] / 60


def _geocoder_bureau(adresse: str) -> dict:
    lieu = _geocode_ban(adresse)
    return {"latitude": lieu["latitude"], "longitude": lieu["longitude"]}


def _ecrire_trajet(conn, ligne: dict) -> None:
    colonnes = list(ligne)
    conn.execute("DELETE FROM trajets WHERE id_salarie = ?", (ligne["id_salarie"],))
    conn.execute(
        f"INSERT INTO trajets ({', '.join(colonnes)}) VALUES ({', '.join('?' for _ in colonnes)})",
        tuple(ligne[col] for col in colonnes),
    )
    conn.commit()


def _arrondi(valeur, decimales: int):
    if valeur is None:
        return None
    return round(float(valeur), decimales)
