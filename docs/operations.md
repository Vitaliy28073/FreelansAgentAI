# Operations

## Local run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill `TELEGRAM_BOT_TOKEN` and `ALLOWED_TELEGRAM_USER_IDS`. Optional: `USER_LLM_API_KEY`, `FREELANCEHUNT_TOKEN`.

```bash
mkdir -p data
python -m app.main
```

SQLite file: `data/radar.db`. Schema is created on startup via `create_all`. Alembic migration `0001_initial` matches the same schema.

## Docker

```bash
# Production database URL inside Compose
# DATABASE_URL=postgresql+asyncpg://radar:radar@postgres:5432/radar
docker compose up --build
```

## Backup

SQLite:

```bash
cp data/radar.db data/radar.db.bak
```

PostgreSQL:

```bash
pg_dump -U radar radar > backup.sql
```

Restore with `psql -U radar radar < backup.sql` or by copying the SQLite file back.

## Health

Telegram `/status` shows connector state, last error code, pause flag and whether LLM is configured. `/sources` shows last successful poll.

If a connector hits 401, set a new official token. If it hits 403 or challenge, leave it paused and check the source in a browser. Do not add proxies.

The first successful poll of a source only stores a cursor. Telegram gets a short init message, not a dump of the current RSS/API page. New listings appear on later polls after filter and analysis.

## Known MVP limits

- One allowlisted owner (multi-user data model is ready, onboarding is personal).
- FL.ru uses RSS summaries, not full HTML pages.
- Freelancehunt bids are never auto-sent.
- Other marketplaces stay disabled.
