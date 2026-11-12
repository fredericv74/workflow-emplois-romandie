# Emplois Romandie — rapport quotidien des offres

Workflow Mistral qui génère chaque matin un rapport des offres d'emploi
**dessinateur projeteur / projeteur** publiées sur jobup.ch dans les régions
**Genève**, **Vaud** et **Vaud / Valais**, et le dépose comme brouillon
dans la boîte Outlook configurée.

## Structure

- `apps/worker/src/worker/workflows/jobs.py` — collecte (jobup.ch, JSON-LD), dédoublonnage, rendu HTML.
- `apps/worker/src/worker/workflows/emplois_romandie.py` — workflow `rapport-emplois-romandie`.
- `apps/worker/src/worker/entrypoints/worker.py` — point d'entrée du worker.
- `deploy/docker/Dockerfile.worker` — image du déploiement géré.
- `tests/` — tests unitaires.

## Entrée du workflow

```json
{
  "max_age_days": 1,
  "recipient": "freddo74000@outlook.fr",
  "dry_run": false
}
```

- `max_age_days` : ne garder que les offres publiées durant les N derniers jours.
- `recipient` : destinataire du brouillon Outlook.
- `dry_run` : si vrai, collecte sans envoyer d'e-mail (test).

## Tests

```bash
uv sync
uv run pytest
```
