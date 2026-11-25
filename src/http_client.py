"""Small HTTP helper. requests carries its own certificate """

from __future__ import annotations

import re
import time

import requests

USER_AGENT = "SportDataSolutionPOC/1.0 (educational data pipeline)"


def url_sans_secret(url: str) -> str:
    return re.sub(r"key=[^&]+", "key=***", url)


def construire_url(base: str, params: dict) -> str:
    return requests.Request("GET", base, params=params).prepare().url


def get_json(url: str, timeout: int = 30, tentatives: int = 3) -> dict:
    dernier : Exception | None = None
    for essai in range(tentatives):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            dernier = exc
        time.sleep(0.4 * (essai + 1))
    raise RuntimeError(f"Appel impossible: {url_sans_secret(url)}")


def post_json(url: str, payload: dict, timeout: int = 15) -> tuple[int, str]:
    response = requests.post(
        url,
        json=payload,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    return response.status_code, response.text
