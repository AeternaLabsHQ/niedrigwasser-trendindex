import httpx
import pytest

from niedrigwasser.niwis import IngestError, NiwisClient

MESSSTELLEN = [
    {"messstelleNr": "S1", "name": "Alpha", "landcode": "DEBY",
     "lizenz": "cc-by/4.0", "messgroesse": ["Abfluss", "Wasserstand"]},
]
ABFLUSS = [
    {"messstelleNr": "S1", "datum": "1992-01-02", "messwert": 10.0, "einheit": "m³/s", "flag": None},
    {"messstelleNr": "S1", "datum": "1992-01-01", "messwert": 12.5, "einheit": "m³/s", "flag": "p"},
]


def _transport(handler):
    return httpx.MockTransport(handler)


def test_client_fetches_stations():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/messstelle")
        return httpx.Response(200, json=MESSSTELLEN)

    c = NiwisClient(transport=_transport(handler), delay_s=0)
    assert c.stations()[0]["messstelleNr"] == "S1"


def test_client_passes_query_params():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["messstelleNr"] == "S1"
        assert request.url.params["von"] == "1992-01-01"
        return httpx.Response(200, json=ABFLUSS)

    c = NiwisClient(transport=_transport(handler), delay_s=0)
    assert len(c.abfluss("S1", "1992-01-01", "1992-01-10")) == 2


def test_client_retries_on_500_then_succeeds():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json=MESSSTELLEN)

    c = NiwisClient(transport=_transport(handler), delay_s=0)
    assert c.stations() == MESSSTELLEN
    assert calls["n"] == 3


def test_client_gives_up_after_3_attempts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    c = NiwisClient(transport=_transport(handler), delay_s=0)
    with pytest.raises(IngestError):
        c.stations()
