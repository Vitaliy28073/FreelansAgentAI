# Freelance Radar AI

Персональный Telegram-ассистент фрилансера: мониторинг разрешённых источников, фильтрация, AI-анализ заказа и черновик первого отклика.

Главное преимущество — качество анализа и первого сообщения. Скорость опроса вторична.

Цепочка MVP:

```text
FL.ru RSS → БД → фильтр → AI-анализ → Telegram-карточка → персональный отклик
```

После проверки качества анализа подключается Freelancehunt API 2.0. Остальные площадки выключены.

## Что умеет

- Читает публичный RSS FL.ru и официальный API Freelancehunt.
- Нормализует и дедуплицирует заказы.
- Фильтрует по профилю, ключевым словам, стоп-словам и бюджету.
- Делает структурированный AI-анализ со score, рисками и объяснением.
- Готовит 3 варианта первого отклика только из фактов профиля.
- Не отправляет отклики на площадки. Копируете текст и открываете исходный заказ.

## Быстрый старт

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

В `.env` обязательно:

- `TELEGRAM_BOT_TOKEN`
- `ALLOWED_TELEGRAM_USER_IDS` — ваш Telegram ID

Опционально:

- `USER_LLM_API_KEY`, `USER_LLM_BASE_URL`, `USER_LLM_MODEL` — свой OpenAI-совместимый ключ
- `FREELANCEHUNT_TOKEN` — токен с https://freelancehunt.com/my/api2
- `FREELANCEHUNT_ENABLED=true`

Без LLM-ключа бот работает: анализ идёт keyword fallback и явно помечается как неполный.

```bash
mkdir -p data
python -m app.main
```

В Telegram: `/start`, затем `/edit_profile`, `/sources`, `/latest`.

Первый опрос источника только запоминает текущую ленту. Карточки и AI-анализ приходят по новым заказам со следующих опросов.

## Тесты

```bash
pytest
ruff check app tests
```

## Docker

```bash
# Для Compose задайте
# DATABASE_URL=postgresql+asyncpg://radar:radar@postgres:5432/radar
docker compose up --build
```

## Документация

- `docs/architecture.md` — архитектура
- `docs/source_compliance_matrix.md` — разрешённые и выключенные источники
- `docs/security.md` — секреты, allowlist, prompt injection
- `docs/operations.md` — запуск, backup, восстановление

## Ограничения MVP

- Один владелец по allowlist.
- FL.ru — только публичный RSS, без HTML-scraping и без автоотклика.
- Freelancehunt bid API не вызывается.
- Kwork, Freelance.ru, YouDo, Upwork, Telegram-каналы выключены до официального доступа.
