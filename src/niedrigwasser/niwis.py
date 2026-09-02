from __future__ import annotations

import time

import httpx

BASE_URL = "https://niwis-online.de/api/daten"


class IngestError(RuntimeError):
    pass


class NiwisClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        transport: httpx.BaseTransport | None = None,
        delay_s: float = 0.3,
    ):
        self._delay_s = delay_s
        self._client = httpx.Client(
            base_url=base_url, transport=transport, timeout=60.0,
            headers={"User-Agent": "niedrigwasser-niedrigwasser-index"},
        )

    def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = self._client.get(path, params=params)
                if resp.status_code < 500:
                    resp.raise_for_status()
                    if self._delay_s:
                        time.sleep(self._delay_s)
                    return resp
                last_exc = IngestError(f"HTTP {resp.status_code} fuer {path}")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
            time.sleep(self._delay_s * (attempt + 1))
        raise IngestError(f"NIWIS-Request fehlgeschlagen nach 3 Versuchen: {path}") from last_exc

    def stations(self) -> list[dict]:
        return self._get("/messstelle").json()

    def stammdaten(self, nr: str) -> dict:
        return self._get("/stammdaten", {"messstelleNr": nr}).json()

    def abfluss(self, nr: str, von: str, bis: str) -> list[dict]:
        return self._get("/abfluss", {"messstelleNr": nr, "von": von, "bis": bis}).json()
