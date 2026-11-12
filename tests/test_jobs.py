"""Tests unitaires pour la collecte et le rendu des offres."""

from datetime import datetime, timedelta, timezone

from worker.workflows.jobs import (
    JobOffer,
    REQUIRED_TITLE_PATTERN,
    _extract_job_postings,
    _parse_posting,
    build_html,
    build_subject,
)

FIXTURE_HTML = """
<html><head>
<script type="application/ld+json">[
{"@context":"https://schema.org","@type":"WebSite","url":"https://www.jobup.ch/"},
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[]},
{"@context":"https://schema.org","@type":"ItemList","numberOfItems":2,"itemListElement":[
{"@type":"ListItem","position":1,"item":{"@context":"https://schema.org","@type":"JobPosting",
"title":"Dessinateur projeteur CVC","identifier":{"@type":"PropertyValue","name":"jobup.ch","value":"abc-123"},
"datePosted":"2026-11-10T08:00:00+01:00","employmentType":"Durée indéterminée",
"hiringOrganization":{"@type":"Organization","name":"Bureau Technique SA"},
"jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Lausanne","addressCountry":"CH"}},
"url":"https://www.jobup.ch/fr/emplois/detail/abc-123/"}},
{"@type":"ListItem","position":2,"item":{"@context":"https://schema.org","@type":"JobPosting",
"title":"Projeteur électricité","identifier":{"@type":"PropertyValue","name":"jobup.ch","value":"def-456"},
"datePosted":"2026-11-09T08:00:00+01:00","employmentType":"Temporaire",
"hiringOrganization":{"@type":"Organization","name":"MAGNETIC SA"},
"jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Carouge","addressCountry":"CH"}},
"url":"https://www.jobup.ch/fr/emplois/detail/def-456/"}}]}
]
</script>
</head><body></body></html>
"""


def test_extract_job_postings():
    postings = _extract_job_postings(FIXTURE_HTML)
    assert len(postings) == 2
    assert postings[0]["title"] == "Dessinateur projeteur CVC"


def test_parse_posting():
    postings = _extract_job_postings(FIXTURE_HTML)
    offer = _parse_posting(postings[0], "Canton de Vaud", "dessinateur projeteur")
    assert offer is not None
    assert offer.job_id == "abc-123"
    assert offer.company == "Bureau Technique SA"
    assert offer.location == "Lausanne"
    assert offer.contract_type == "Durée indéterminée"
    assert offer.region_label == "Canton de Vaud"
    assert offer.posted_at.tzinfo is not None


def test_parse_posting_invalid():
    assert _parse_posting({"title": "pas d'id"}, "Région", "terme") is None
    assert (
        _parse_posting(
            {"identifier": {"value": "x"}, "title": "t", "datePosted": "n/a"},
            "Région",
            "terme",
        )
        is None
    )


def _offer(days_ago: int, job_id: str = "id-1") -> JobOffer:
    return JobOffer(
        job_id=job_id,
        title="Dessinateur projeteur",
        company="ACME SA",
        location="Genève",
        url="https://www.jobup.ch/fr/emplois/detail/x/",
        posted_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        contract_type="Durée indéterminée",
        region_label="Canton de Genève",
        term="dessinateur projeteur",
    )


def test_build_subject_and_html_with_offers():
    offers = [_offer(0), _offer(1, "id-2")]
    subject = build_subject(offers, datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc))
    assert "12/11/2026" in subject
    assert "2 offre(s)" in subject
    html = build_html(offers, datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc))
    assert "ACME SA" in html
    assert "https://www.jobup.ch/fr/emplois/detail/x/" in html
    assert "Canton de Genève" in html


def test_required_title_pattern():
    assert REQUIRED_TITLE_PATTERN.search("Dessinateur-trice en architecture")
    assert REQUIRED_TITLE_PATTERN.search("2 Dessinateurs(trice) Projeteurs(euses) Électricité")
    assert REQUIRED_TITLE_PATTERN.search("Projeteur - Technicien CVC - Revit (H/F)")
    assert not REQUIRED_TITLE_PATTERN.search("Graphiste (H/F)")
    assert not REQUIRED_TITLE_PATTERN.search("Ingénieur Chef de Projet Électricité")


def test_build_html_empty():
    html = build_html([], datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc))
    assert "Aucune nouvelle offre" in html
