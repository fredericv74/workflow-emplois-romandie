"""Workflow quotidien : rapport des offres dessinateur projeteur / projeteur en Suisse romandie."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import mistralai.workflows as workflows
from mistralai.workflows import Depends
from mistralai.workflows.plugins.mistralai.connectors import (
    ToolCallClient,
    connector,
    uses_connectors,
)
from pydantic import BaseModel

from worker.workflows.jobs import (
    JobOffer,
    build_html,
    build_subject,
    collect_offers,
)

resend_connector = connector("resend_6115", run_as="deployment")

SENDER = "Rapport Emplois <onboarding@resend.dev>"
DEFAULT_RECIPIENT = "freddoduleman@gmail.com"


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
    subject: str,
    body_html: str,
    recipient: str,
    resend: ToolCallClient = Depends(resend_connector),
) -> str:
    result: Any = await resend.call_tool(
        tool_name="send_email",
        arguments={
            "from": SENDER,
            "to": [recipient],
            "subject": subject,
            "html": body_html,
        },
    )
    return str(result)


@workflows.workflow.define(
    name="rapport-emplois-romandie",
    workflow_display_name="Rapport emplois Romandie",
    workflow_description=(
        "Rapport quotidien des offres d'emploi dessinateur projeteur / projeteur "
        "dans les cantons de Genève, Vaud et Valais, envoyé par e-mail via Resend."
    ),
)
@uses_connectors(resend_connector)
class RapportEmploisRomandieWorkflow:
    @workflows.workflow.entrypoint
    async def run(self, input: ReportInput) -> ReportOutput:
        offers = await collect_offers_activity(input.max_age_days)
        now = datetime.now(timezone.utc)
        subject = build_subject(offers, now)
        emailed = False
        if not input.dry_run:
            await send_report_email_activity(
                subject=subject,
                body_html=build_html(offers, now),
                recipient=input.recipient,
            )
            emailed = True
        return ReportOutput(
            offers_count=len(offers),
            subject=subject,
            emailed=emailed,
        )
