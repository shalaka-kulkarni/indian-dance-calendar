from pipeline.scrapers.sitemap import _parse_sitemap, discover_event_urls

INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://venue.org/sitemap-events.xml</loc></sitemap>
  <sitemap><loc>https://venue.org/sitemap-staff.xml</loc></sitemap>
</sitemapindex>"""

EVENTS = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://venue.org/events/kathak-night</loc><lastmod>2026-08-01</lastmod></url>
  <url><loc>https://venue.org/events/odissi-evening</loc><lastmod>2026-08-09</lastmod></url>
  <url><loc>https://venue.org/events/category/dance/</loc><lastmod>2026-08-05</lastmod></url>
  <url><loc>https://venue.org/about</loc><lastmod>2026-08-04</lastmod></url>
</urlset>"""


class FakeResponse:
    def __init__(self, text, code=200):
        self.text, self.status_code = text, code


class FakeClient:
    def __init__(self, pages):
        self.pages = pages

    def get(self, url, **kw):
        if url in self.pages:
            return FakeResponse(self.pages[url])
        return FakeResponse("not found", 404)


def test_parse_sitemap_splits_children_and_pages():
    children, pages = _parse_sitemap(INDEX)
    assert children == [
        "https://venue.org/sitemap-events.xml",
        "https://venue.org/sitemap-staff.xml",
    ]
    assert pages == []
    children, pages = _parse_sitemap(EVENTS)
    assert children == []
    assert len(pages) == 4


def test_discover_follows_event_sitemap_and_filters(monkeypatch):
    client = FakeClient({
        "https://venue.org/sitemap.xml": INDEX,
        "https://venue.org/sitemap-events.xml": EVENTS,
    })
    urls = discover_event_urls(client, "https://venue.org/whats-on")
    # Event pages only, newest first; category and about pages excluded.
    assert urls == [
        "https://venue.org/events/odissi-evening",
        "https://venue.org/events/kathak-night",
    ]
