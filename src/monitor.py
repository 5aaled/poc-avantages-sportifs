"""Print the current decision: headcount and cost, from the four warehouse tables."""

from __future__ import annotations

from src.db import connect, init_db


def afficher() -> None:
    conn = connect()
    init_db(conn)
    effectif = conn.execute("SELECT COUNT(*) FROM employes").fetchone()[0]
    if effectif == 0:
        print("Aucun salarié en base. Lancez: python -m src.pipeline")
        conn.close()
        return

    ligne = conn.execute(
        """
        SELECT
            COUNT(*) AS nb_salaries,
            COALESCE(SUM(eligible_prime), 0) AS nb_eligible_prime,
            COALESCE(SUM(eligible_bien_etre), 0) AS nb_eligible_bien_etre,
            COALESCE(SUM(montant_prime), 0) AS cout_primes,
            COALESCE(SUM(cout_jours_bien_etre), 0) AS cout_jours_bien_etre,
            COALESCE(SUM(cout_total), 0) AS cout_total,
            MAX(taux_prime) AS taux_prime,
            MAX(calcule_le) AS calcule_le
        FROM eligibilite
        """
    ).fetchone()
    anomalies = conn.execute("SELECT COUNT(*) FROM trajets WHERE est_anomalie = 1").fetchone()[0]
    activites = conn.execute("SELECT COUNT(*) FROM activites").fetchone()[0]
    print(f"Décision en cours, calculée le {ligne['calcule_le']}")
    print(f"  salariés                  {ligne['nb_salaries']}")
    print(f"  éligibles à la prime      {ligne['nb_eligible_prime']}")
    print(f"  éligibles bien-être       {ligne['nb_eligible_bien_etre']}")
    print(f"  anomalies de trajet       {anomalies}")
    print(f"  activités                 {activites}")
    print(f"  taux                      {float(ligne['taux_prime']):.0%}")
    print(f"  coût des primes           {ligne['cout_primes']:,.2f} €".replace(",", " "))
    print(f"  coût des jours bien-être  {ligne['cout_jours_bien_etre']:,.2f} €".replace(",", " "))
    print(f"  coût total                {ligne['cout_total']:,.2f} €".replace(",", " "))
    conn.close()


def main() -> None:
    afficher()


if __name__ == "__main__":
    main()
