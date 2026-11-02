# Security

- Secrets live in environment variables. `.env` is gitignored.
- LLM keys use `USER_LLM_API_KEY` / `USER_LLM_BASE_URL` / `USER_LLM_MODEL`. The app never reads Agent runtime keys.
- Freelancehunt token is stored encrypted in `source_credentials` when saved from env. Logs redact token/authorization/api_key fields.
- Telegram access is an allowlist: `ALLOWED_TELEGRAM_USER_IDS`.
- Callbacks always load the job by id and the acting Telegram user from the server session. There is no trust of client-supplied ownership.
- Job URLs are accepted only from connector payloads of allowed hosts (`fl.ru`, `freelancehunt.com`).
- Attachments from listings are not downloaded.
- Prompt injection in a job description is treated as listing text and may raise a risk flag.
- `/delete_me` removes the user, profile, analyses, drafts, connector rows and related events.
- The bot never asks for freelance-exchange passwords, OTP or cookies.
- Bid/send API on Freelancehunt is not invoked.
