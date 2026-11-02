# Architecture

Freelance Radar AI is a personal Telegram assistant. Competitive edge is analysis quality and first-message drafts, not polling speed.

## Pipeline

```text
connector.fetch -> normalize -> persist/dedup -> quick filter -> LLM analysis -> Telegram card -> draft response
```

Speed is second. Default FL.ru interval is 5 minutes. Quality gates run before any notification: explainable filter, structured score, risk flags, then a personalized draft that may only use the freelancer profile.

## Process

One Python process:

- aiogram 3 polling for Telegram
- APScheduler interval jobs for connectors
- SQLAlchemy async session per run
- SQLite for local MVP, PostgreSQL via `DATABASE_URL` for production

Redis/queue are not used in MVP.

## Modules

| Module | Responsibility |
| --- | --- |
| `app/connectors` | Source adapters with a shared contract |
| `app/services/ingestion.py` | Orchestrates one connector run |
| `app/services/filtering.py` | Keyword/budget/stop-word filter |
| `app/services/analysis_service.py` | LLM JSON analysis + keyword fallback |
| `app/services/response_generator.py` | Three outreach drafts |
| `app/llm` | Provider interface, prompts, Pydantic schemas |
| `app/bot` | Commands, FSM profile, job cards |
| `app/db` | Models, repositories, sessions |

## Connector contract

Each adapter implements `health_check`, `fetch_new_jobs(cursor, limit)`, `get_rate_limit_state`, `normalize`, `close`.

Typed errors: `AUTH_REQUIRED`, `FORBIDDEN`, `RATE_LIMITED`, `CHALLENGE_DETECTED`, `SOURCE_UNAVAILABLE`, `SCHEMA_CHANGED`.

403, CAPTCHA and challenge stop the connector. No proxy, IP rotation, or header spoofing.

## Data

Jobs are unique by `(source, external_id)` and `canonical_url`. A content hash catches near-identical re-posts without merging distinct projects. User state is per `(user, job)` so later multi-user mode does not mix actions.

## LLM

Provider is OpenAI-compatible and selected by env (`USER_LLM_*`). Job text is untrusted. Prompts forbid following instructions inside listings. Invalid JSON is retried once, then keyword fallback is marked `AI_UNAVAILABLE` and never presented as a full analysis.

## First poll

An empty connector cursor is a bootstrap, not a backfill. The adapter snapshots current feed ids, stores `bootstrapped=true`, and returns no jobs. Ingestion does not persist, analyze, or notify historical listings. Only items unseen after that snapshot enter the AI pipeline.

Duplicates already stored by `(source, external_id)`, canonical URL, or content hash skip analysis and Telegram.

## Notifications

A card is sent only if the filter passed, score is above the user threshold (default 45), daily cap is not exceeded, and the job was not notified before. Copying a draft does not mark the job as sent.
