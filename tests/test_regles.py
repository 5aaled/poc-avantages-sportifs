"""Numbered examples of the business rules. They do not call the map."""

from src.eligibility import calculer_eligibilite_salarie, evaluer_trajet

PARAMS = {
    "taux_prime": 0.05,
    "seuil_activites": 15,
    "jours_bien_etre": 5,
    "distance_max_marche_km": 15,
    "distance_max_velo_km": 25,
    "jours_ouvrables_an": 218,
    "score_geocodage_min": 0.5,
}


def test_marche_15_km_accepte_et_15_1_refuse():
    assert evaluer_trajet("Marche/running", 15, 0.9, PARAMS)["est_anomalie"] == 0
    assert evaluer_trajet("Marche/running", 15.1, 0.9, PARAMS)["est_anomalie"] == 1


def test_velo_25_km_accepte_et_au_dessus_refuse():
    assert evaluer_trajet("Vélo/Trottinette/Autres", 25, 0.8, PARAMS)["est_anomalie"] == 0
    assert evaluer_trajet("Vélo/Trottinette/Autres", 25.1, 0.8, PARAMS)["est_anomalie"] == 1


def test_adresse_mal_reconnue_retire_la_prime():
    verdict = evaluer_trajet("Marche/running", 4, 0.3, PARAMS)
    assert verdict["est_anomalie"] == 1


def test_quinze_seances_donnent_les_jours_quatorze_non():
    atteint = calculer_eligibilite_salarie(40000, "Marche/running", 0, "ok", 15, PARAMS)
    assert atteint["eligible_prime"] == 1
    assert atteint["montant_prime"] == 2000
    assert atteint["eligible_bien_etre"] == 1
    assert atteint["jours_bien_etre"] == 5

    en_dessous = calculer_eligibilite_salarie(40000, "Marche/running", 0, "ok", 14, PARAMS)
    assert en_dessous["eligible_bien_etre"] == 0
    assert en_dessous["cout_jours_bien_etre"] == 0


def test_anomalie_retire_la_prime_et_laisse_les_jours():
    resultat = calculer_eligibilite_salarie(40000, "Marche/running", 1, "adresse à vérifier", 20, PARAMS)
    assert resultat["eligible_prime"] == 0
    assert resultat["montant_prime"] == 0
    assert resultat["eligible_bien_etre"] == 1
