from __future__ import annotations

import argparse
import sqlite3
import uuid
from datetime import datetime

import pandas as pd

import config
from src.activities import generer_activites
from src.db import connect, horodatage, init_db
from src.distances import calculer_trajets
from src.eligibility import recalculer
from src.export import exporter
from src.extract import charger_sources
from src.journal import Journal
from src.quality import a_des_echecs, controler_resultats, controler_sources

COLONNES_EMPLOYES = [
    "id_salarie",
    "nom",
    "prenom",
    "date_naissance",
    "bu",
    "date_embauche",
    "salaire_brut",
    "type_contrat",
    "jours_cp",
    "adresse_domicile",
    "moyen_deplacement",
    "sport",
]

COLONNES_ACTIVITES = [
    "id",
    "id_salarie",
    "date_debut",
    "date_fin",
    "type_activite",
    "distance_m",
    "commentaire",
    "message_slack",
    "cree_le",
]


def executer(reconstruire_activites: bool = False, reconstruire_distances: bool = False) -> int:
    params = config.load_parameters()
    maintenant = datetime.now().replace(microsecond=0)
    run_id = maintenant.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:4]

    conn = connect()
    init_db(conn)
    journal = Journal(run_id)
    print(f"Exécution {run_id}", flush=True)
    print("Distances via la Base Adresse Nationale et OpenStreetMap.", flush=True)

    try:
        debut = datetime.now()
        employes = charger_sources()
        _remplacer_employes(conn, employes)
        journal.enregistrer(
            "extraction",
            debut,
            "ok",
            lignes_lues=len(employes),
            lignes_ecrites=len(employes),
            message=f"{len(employes)} salariés chargés depuis les fichiers Excel",
        )

        debut = datetime.now()
        calcules, deja_en_cache = calculer_trajets(
            conn, employes, params, reconstruire_distances, maintenant
        )
        journal.enregistrer(
            "distances",
            debut,
            "ok",
            lignes_lues=len(employes),
            lignes_ecrites=calcules,
            message=f"{calcules} trajet(s) calculé(s), {deja_en_cache} déjà en cache",
        )

        debut = datetime.now()
        nouvelles = _synchroniser_activites(conn, employes, params, reconstruire_activites, maintenant)
        total_activites = conn.execute("SELECT COUNT(*) FROM activites").fetchone()[0]
        journal.enregistrer(
            "activites",
            debut,
            "ok",
            lignes_lues=len(employes),
            lignes_ecrites=nouvelles,
            message=f"{nouvelles} nouvelle(s) séance(s), {total_activites} au total",
        )

        debut = datetime.now()
        controles = controler_sources(conn, maintenant)
        journal.enregistrer(
            "qualite_sources",
            debut,
            "echec" if a_des_echecs(controles) else "ok",
            lignes_ecrites=len(controles),
            message=_resume_controles(controles),
        )

        debut = datetime.now()
        totaux = recalculer(conn, params, maintenant)
        controles_resultats = controler_resultats(conn, params)
        controles.extend(controles_resultats)
        exporter(conn)
        statut = "echec" if a_des_echecs(controles) else "ok"
        journal.enregistrer(
            "indicateurs",
            debut,
            statut,
            lignes_ecrites=totaux["nb_salaries"],
            message=(
                f"prime {totaux['cout_primes']:.0f} €, "
                f"jours bien-être {totaux['cout_jours_bien_etre']:.0f} €, "
                f"total {totaux['cout_total']:.0f} €"
            ),
        )
    except Exception as exc:
        print(f"[echec] pipeline interrompu: {exc}", flush=True)
        conn.close()
        return 1

    _afficher_synthese(totaux, controles)
    conn.close()
    return 1 if a_des_echecs(controles) else 0


def _remplacer_employes(conn: sqlite3.Connection, employes: pd.DataFrame) -> None:
    conn.execute("DELETE FROM employes")
    lignes = []
    for ligne in employes.to_dict(orient="records"):  # orient="records" transforms a DataFrame into a list of row-based dictionaries,
        sport = ligne["sport"]
        lignes.append(
            (
                int(ligne["id_salarie"]),
                ligne["nom"],
                ligne["prenom"],
                _date_iso(ligne["date_naissance"]),
                ligne["bu"],
                _date_iso(ligne["date_embauche"]),
                float(ligne["salaire_brut"]),
                ligne["type_contrat"],
                int(ligne["jours_cp"]),
                ligne["adresse_domicile"],
                ligne["moyen_deplacement"],
                None if pd.isna(sport) else sport,
            )
        )
    conn.executemany(
        f"INSERT INTO employes ({', '.join(COLONNES_EMPLOYES)}) VALUES ({', '.join('?' for _ in COLONNES_EMPLOYES)})",
        lignes,
    )
    conn.commit()



# synchronizes employees' sports activities between the DataFrame and SQLite database by removing obsolete activities, identifying employees who need activities, generating them, and inserting them into the database.
def _synchroniser_activites(conn, employes, params, reconstruire: bool, maintenant: datetime) -> int:
    if reconstruire:
        conn.execute("DELETE FROM activites")
    ids_sport = [
        int(identifiant)
        for identifiant in employes.loc[employes["sport"].notna(), "id_salarie"].tolist()
    ]
    if ids_sport:
        marques = ",".join("?" for _ in ids_sport)
        conn.execute(
            f"DELETE FROM activites WHERE id_salarie NOT IN ({marques})",
            ids_sport,
        )
    else:
        conn.execute("DELETE FROM activites")
    conn.commit()

    deja = {int(row[0]) for row in conn.execute("SELECT DISTINCT id_salarie FROM activites")}
    manquants = employes[employes["sport"].notna() & ~employes["id_salarie"].isin(deja)]
    nouvelles = generer_activites(manquants, params, maintenant)
    if nouvelles.empty:
        return 0
    prochain = conn.execute("SELECT COALESCE(MAX(id), 0) FROM activites").fetchone()[0] + 1
    lignes = []
    for decalage, ligne in enumerate(nouvelles.to_dict(orient="records")):
        lignes.append(
            (
                prochain + decalage,
                int(ligne["id_salarie"]),
                horodatage(ligne["date_debut"]),
                horodatage(ligne["date_fin"]),
                ligne["type_activite"],
                ligne["distance_m"],
                ligne["commentaire"],
                ligne["message_slack"],
                horodatage(ligne["cree_le"]),
            )
        )
    conn.executemany(
        f"INSERT INTO activites ({', '.join(COLONNES_ACTIVITES)}) VALUES ({', '.join('?' for _ in COLONNES_ACTIVITES)})",
        lignes,
    )
    conn.commit()
    return len(lignes)

# here it convert the date to str because sqlite doenst have date as datatype
def _date_iso(valeur) -> str:
    if hasattr(valeur, "isoformat"):
        return valeur.isoformat()
    return str(valeur)[:10]


def _resume_controles(controles: list[dict]) -> str:
    echecs = sum(controle["statut"] == "echec" for controle in controles)
    avertissements = sum(controle["statut"] == "avertissement" for controle in controles)
    return f"{len(controles) - echecs - avertissements} ok, {avertissements} avertissement(s), {echecs} échec(s)"

# Display the final pipeline summary in the terminal.
def _afficher_synthese(synthese: dict, controles: list[dict]) -> None:
    print("", flush=True)
    print("Synthèse", flush=True)
    print(f"  salariés                  {synthese['nb_salaries']}", flush=True)
    print(f"  éligibles à la prime      {synthese['nb_eligible_prime']}", flush=True)
    print(f"  éligibles bien-être       {synthese['nb_eligible_bien_etre']}", flush=True)
    print(f"  anomalies de trajet       {synthese['nb_anomalies_trajet']}", flush=True)
    print(f"  activités                 {synthese['nb_activites']}", flush=True)
    print(f"  coût des primes           {synthese['cout_primes']:,.2f} €".replace(",", " "), flush=True)
    print(f"  coût des jours bien-être  {synthese['cout_jours_bien_etre']:,.2f} €".replace(",", " "), flush=True)
    print(f"  coût total                {synthese['cout_total']:,.2f} €".replace(",", " "), flush=True)
    print("Contrôles", flush=True)
    for controle in controles:
        print(f"  [{controle['statut']}] {controle['controle']}: {controle['detail']}", flush=True)
    print(f"Base     {config.DB_PATH}", flush=True)
    print(f"Exports  {config.OUTPUT_DIR}", flush=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pipeline des avantages sportifs")
    parser.add_argument(
        "--rebuild-activities",
        action="store_true",
        help="Efface les séances et les recrée.",
    )
    parser.add_argument(
        "--rebuild-distances",
        action="store_true",
        help="Recalcule toutes les distances domicile-bureau.",
    )
    args = parser.parse_args(argv)
    code = executer(args.rebuild_activities, args.rebuild_distances)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
