"""Workflow quotidien : rapport des offres dessinateur projeteur / projeteur en Suisse romandie."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import mistralai.workflows as workflows
from pydantic import BaseModel

from worker.workflows.jobs import (
    JobOffer,
    build_html,
    build_subject,
    collect_offers,
)

SENDER = "Rapport Emplois <onboarding@resend.dev>"
DEFAULT_RECIPIENT = "freddoduleman@gmail.com"
RESEND_API_URL = "https://api.resend.com/emails"


class ReportInput(BaseModel):
    max_age_days: int = 1
    recipient: str = DEFAULT_RECIPIENT
    dry_run: bool = False


class ReportOutput(BaseModel):
    offers_count: int
    subject: str
    emailed: bool


@workflows.activity(name="collect-offers")
async def collect_offers_activity(max_age_days: int) -> list[JobOffer]:
    return await collect_offers(max_age_days=max_age_days)


@workflows.activity(name="send-report-email")
async def send_report_email_activity(
    offers: list[JobOffer],
    recipient: str,
    dry_run: bool,
) -> str:
    now = datetime.now(timezone.utc)
    subject = build_subject(offers, now)
    if dry_run:
        return subject
    body_html = build_html(offers, now)
    import httpx

    api_key = os.environ.get("RESEND_API_KEY") or os.environ["resend_api_key"]
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": SENDER,
                "to": [recipient],
                "subject": subject,
                "html": body_html,
            },
        )
    response.raise_for_status()
    return subject


@workflows.workflow.define(
    name="rapport-emplois-romandie",
    workflow_display_name="Rapport emplois Romandie",
    workflow_description=(
        "Rapport quotidien des offres d'emploi dessinateur projeteur / projeteur "
        "dans les cantons de Genève, Vaud et Valais, envoyé par e-mail via Resend."
    ),
)
class RapportEmploisRomandieWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: ReportInput) -> ReportOutput:
        offers = await collect_offers_activity(input.max_age_days)
        subject = await send_report_email_activity(
            offers=offers,
            recipient=input.recipient,
            dry_run=input.dry_run,
        )
        return ReportOutput(
            offers_count=len(offers),
            subject=subject,
            emailed=not input.dry_run,
        )
