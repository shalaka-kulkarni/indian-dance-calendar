import httpx

from pipeline.scrapers.tribe import tribe_events

PAYLOAD = {
    "events": [
        {
            "title": "Sarod Recital: Amjad Ali Khan",
            "url": "https://venue.org/event/sarod/",
            "start_date": "2026-11-14 20:00:00",
            "end_date": "2026-11-14 22:00:00",
            "description": "<p>An evening of <b>raga</b>.</p>",
            "cost": "$25 - $60",
            "cost_details": {"currency_symbol": "$", "values": [25, 60]},
            "venue": {
                "venue": "Colden Auditorium",
                "address": "153-49 Reeves Ave",
                "city": "Queens",
                "state": "NY",
            },
            "website": "https://tickets.example.org/sarod",
        },
        {
            "title": "Free Community Concert",
            "url": "https://venue.org/event/free/",
            "start_date": "2026-12-01 19:30:00",
            "cost_details": {"currency_symbol": "$", "values": []},
            "cost": "Free",
            "venue": {},
        },
    ]
}


class FakeResponse:
    def __init__(self, payload, code=200):
        self._payload, self.status_code = payload, code

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeClient:
    """Serves the API on the first page and an empty list after."""

    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.pages.pop(0) if self.pages else FakeResponse({"events": []})


def test_tribe_reads_events_from_the_plugin_api():
    client = FakeClient([FakeResponse(PAYLOAD)])
    events = tribe_events(client, "kupferberg", "https://venue.org/events/")

    assert client.calls[0].startswith("https://venue.org/wp-json/tribe/events/v1/events")
    assert len(events) == 2

    sarod = events[0]
    assert sarod.title == "Sarod Recital: Amjad Ali Khan"
    assert sarod.start_raw == "2026-11-14 20:00:00"
    assert sarod.venue == "Colden Auditorium"
    assert sarod.address == "153-49 Reeves Ave, Queens, NY"
    assert sarod.price_raw == "$25-$60"
    assert sarod.info_url == "https://venue.org/event/sarod/"
    assert sarod.ticket_url == "https://tickets.example.org/sarod"
    # Description comes through as text, not markup.
    assert "<b>" not in sarod.description
    assert "raga" in sarod.description


def test_tribe_falls_back_to_the_cost_string_when_no_values():
    events = tribe_events(FakeClient([FakeResponse(PAYLOAD)]), "v", "https://venue.org/e/")
    assert events[1].price_raw == "Free"


def test_tribe_returns_nothing_for_a_site_without_the_plugin():
    assert tribe_events(FakeClient([FakeResponse(None, 404)]), "v", "https://venue.org/e/") == []


def test_tribe_survives_a_dead_endpoint():
    class Boom(FakeClient):
        def get(self, url, **kwargs):
            raise httpx.ConnectError("no route")

    assert tribe_events(Boom([]), "v", "https://venue.org/e/") == []
