"""Print one line per pipeline step. The log is not stored."""

from __future__ import annotations

from datetime import datetime


class Journal:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def enregistrer(
        self,
        etape: str,  debut: datetime,  statut: str,  lignes_lues: int | None = None, lignes_ecrites: int | None = None,
        message: str = "",
    ) -> None:
        volumes = f"lues {lignes_lues if lignes_lues is not None else '-'}, écrites {lignes_ecrites if lignes_ecrites is not None else '-'}"
        suffixe = f" — {message}" if message else ""
        print(
            f"[{statut}] {self.run_id} {etape} dès {debut:%H:%M:%S} ({volumes}){suffixe}",
            flush=True,
        )

        #flush=True forces Python to send the printed output to the terminal immediately instead of keeping it temporarily in the output buffer.
