"""Collecte des offres d'emploi jobup.ch pour dessinateur projeteur / projeteur."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from pydantic import BaseModel

SEARCH_URL = "https://www.jobup.ch/fr/emplois/"
USER_AGENT = "Mozilla/5.0 (compatible; emplois-romandie-workflow/0.1)"

TERMS = ["dessinateur projeteur", "projeteur"]

REQUIRED_TITLE_PATTERN = re.compile(r"dessinat|projeteur", re.IGNORECASE)

REGIONS: list[tuple[str, int]] = [
    ("Canton de Genève", 34),
    ("Canton de Vaud", 52),
    ("Région Vaud / Valais", 10),
]


class JobOffer(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    url: str
    posted_at: datetime
    contract_type: str = ""
    region_label: str
    term: str


def _extract_job_postings(html: str) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []
    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "ItemList":
                for element in item.get("itemListElement", []):
                    job = element.get("item", {})
                    if job.get("@type") == "JobPosting":
                        postings.append(job)
    return postings


def _parse_posting(job: dict[str, Any], region_label: str, term: str) -> JobOffer | None:
    job_id = (job.get("identifier") or {}).get("value") or ""
    title = job.get("title") or ""
    if not job_id or not title:
        return None
    posted_raw = job.get("datePosted")
    try:
        posted_at = datetime.fromisoformat(posted_raw)
    except (TypeError, ValueError):
        return None
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    organization = job.get("hiringOrganization") or {}
    location = ((job.get("jobLocation") or {}).get("address") or {}).get(
        "addressLocality", ""
    )
    return JobOffer(
        job_id=job_id,
        title=title,
        company=organization.get("name", ""),
        location=location,
        url=job.get("url", ""),
        posted_at=posted_at,
        contract_type=job.get("employmentType", ""),
        region_label=region_label,
        term=term,
    )


async def fetch_search(
    client: httpx.AsyncClient, term: str, region_label: str, region_code: int
) -> list[JobOffer]:
    response = await client.get(
        SEARCH_URL,
        params={"term": term, "region": region_code},
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    offers = [
        offer
        for job in _extract_job_postings(response.text)
        if (offer := _parse_posting(job, region_label, term)) is not None
    ]
    return offers


async def collect_offers(max_age_days: int = 1) -> list[JobOffer]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    seen: dict[str, JobOffer] = {}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for term in TERMS:
            for region_label, region_code in REGIONS:
                for offer in await fetch_search(client, term, region_label, region_code):
                    if (
                        offer.posted_at >= cutoff
                        and REQUIRED_TITLE_PATTERN.search(offer.title)
                        and offer.job_id not in seen
                    ):
                        seen[offer.job_id] = offer
    return sorted(seen.values(), key=lambda o: o.posted_at, reverse=True)


def build_subject(offers: list[JobOffer], day: datetime) -> str:
    day_str = day.strftime("%d/%m/%Y")
    return f"Rapport emplois {day_str} : {len(offers)} offre(s) dessinateur projeteur / projeteur (GE-VD-VS)"


def build_html(offers: list[JobOffer], day: datetime) -> str:
    day_str = day.strftime("%d/%m/%Y")
    if not offers:
        return (
            f"<p>Bonjour Frédéric,</p>"
            f"<p>Aucune nouvelle offre <b>dessinateur projeteur / projeteur</b> "
            f"publiée depuis hier sur jobup.ch pour Genève, Vaud et Valais (rapport du {day_str}).</p>"
            f"<p>Recherches utilisées : « dessinateur projeteur » et « projeteur ».</p>"
        )
    by_region: dict[str, list[JobOffer]] = {}
    for offer in offers:
        by_region.setdefault(offer.region_label, []).append(offer)
    rows = []
    for offer in offers:
        posted = offer.posted_at.strftime("%d/%m/%Y")
        rows.append(
            "<tr>"
            f'<td><a href="{offer.url}">{offer.title}</a></td>'
            f"<td>{offer.company}</td>"
            f"<td>{offer.location}</td>"
            f"<td>{offer.contract_type}</td>"
            f"<td>{posted}</td>"
            "</tr>"
        )
    sections = []
    for region_label, region_offers in by_region.items():
        sections.append(f"<li><b>{region_label}</b> : {len(region_offers)} offre(s)</li>")
    return (
        f"<p>Bonjour Frédéric,</p>"
        f"<p>Voici le rapport du <b>{day_str}</b> : "
        f"<b>{len(offers)}</b> offre(s) publiée(s) récemment sur jobup.ch.</p>"
        f"<ul>{''.join(sections)}</ul>"
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">'
        "<tr style=\"background-color:#e8eef7;\"><th>Poste</th><th>Entreprise</th><th>Lieu</th><th>Contrat</th><th>Publié le</th></tr>"
        f"{''.join(rows)}"
        "</table>"
        "<p style=\"color:#666;font-size:12px;\">Source : jobup.ch — recherches « dessinateur projeteur » et « projeteur », régions Genève, Vaud, Vaud/Valais.</p>"
    )
