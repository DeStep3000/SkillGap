# SkillGap

MVP-гибридного карьерного ассистента для одной роли: `Python Web Developer`.

Сейчас проект уже содержит:

- `FastAPI`-backend с data-driven матрицей компетенций.
- rule-based assessment engine с уровнями `Junior`, `Middle`, `Senior`.
- Telegram-бота на `aiogram`, который ведет пользователя по анкете.
- хранение истории оценок в `PostgreSQL`.
- контейнерный запуск через `Docker` и `docker compose`.
- управление зависимостями через `uv`.
- LLM-слой через `OpenRouter` с возможностью использовать разные модели под разные задачи.

## Что умеет MVP

1. Пользователь открывает бота и выбирает роль `Python Web Developer`.
2. Бот задает вопросы по матрице компетенций: часть кнопками, часть свободным текстом.
3. Свободный текст отправляется в OpenRouter на extraction и превращается в структурированный профиль.
4. Backend считает баллы, определяет текущий уровень и покрытие матрицы.
5. Пользователь получает:
   - текущий уровень;
   - объяснение результата;
   - gaps до цели;
   - roadmap;
   - идеи мини-проектов.
6. Результат сохраняется в историю, ее можно открыть командой `/history`.
7. После оценки можно вставить текст вакансии и получить vacancy match с gaps.

## Структура

```text
app/
  api.py
  config.py
  main.py
  repository.py
  schemas.py
  data/python_web_developer.json
  services/
    assessment.py
    catalog.py
    llm_service.py
bot/
  client.py
  config.py
  formatters.py
  keyboards.py
  main.py
  states.py
```

## Быстрый запуск

```bash
cp .env.example .env
```

Заполни `.env`, минимум нужен `BOT_TOKEN`.

Запуск всего стека в Docker:

```bash
docker compose up --build
```

После старта будут доступны:

- API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## Локальный запуск через uv

Если хочешь запускать без Docker, сначала нужен поднятый PostgreSQL и заполненный `.env`.

Установи зависимости:

```bash
uv sync
```

Подними API:

```bash
uv run uvicorn app.main:app --reload
```

Во втором терминале запусти бота:

```bash
uv run python -m bot.main
```

## API

- `GET /health`
- `GET /api/v1/reference/roles`
- `GET /api/v1/reference/roles/{role_id}/questionnaire`
- `POST /api/v1/assessments`
- `GET /api/v1/users/{telegram_id}/history`
- `GET /api/v1/users/{telegram_id}/history/{assessment_id}`
- `POST /api/v1/users/{telegram_id}/vacancy-analyses`

## OpenRouter и несколько моделей

С `OpenRouter` не нужно получать отдельный ключ на каждую нейросеть.
Логика такая:

- один `OPENROUTER_API_KEY`
- для каждой задачи свой `model id`

Пример разделения:

- `OPENROUTER_EXTRACTION_MODEL` — модель для извлечения структуры из свободного текста
- `OPENROUTER_EXPLANATION_MODEL` — модель для human-readable explanation и roadmap
- `OPENROUTER_VACANCY_MODEL` — модель для анализа вакансии

То есть внутри проекта можно вызывать один и тот же API OpenRouter, но в поле `model` передавать разные значения для разных шагов пайплайна.

Сейчас в коде уже подключены:

- free-text extraction для текстовых ответов анкеты
- explanation для итогового human-readable результата
- vacancy extraction и vacancy matching по тексту вакансии

То есть один и тот же OpenRouter key у тебя уже покрывает три сценария: extraction профиля, explanation результата и extraction требований вакансии.

## Где менять матрицу

Основная предметная логика лежит в файле:

- `app/data/python_web_developer.json`

Там можно править:

- вопросы;
- уровни и пороги;
- веса компетенций;
- gap-логику;
- мини-проекты.

## Следующий шаг

После этого MVP можно без смены архитектуры расширять:

- другими IT-ролями через новые JSON-матрицы;
- vacancy matching;
- LLM extraction для свободного текста;
- более детальной аналитикой прогресса.
