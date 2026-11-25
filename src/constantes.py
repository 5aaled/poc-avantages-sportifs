"""Commute modes as they appear in the HR file, and the route profile of each."""

from __future__ import annotations

# mode de déplacement -> profil d'itinéraire
MODES_ITINERAIRE = {
    "Marche/running": "walking",
    "Vélo/Trottinette/Autres": "bicycling",
    "Transports en commun": "transit",
    "véhicule thermique/électrique": "driving",
}

# Modes soumis au contrôle de distance, et le paramètre qui porte le seuil.
SEUIL_PARAM = {
    "Marche/running": "distance_max_marche_km",
    "Vélo/Trottinette/Autres": "distance_max_velo_km",
}

MODES_SPORTIFS = tuple(SEUIL_PARAM)
