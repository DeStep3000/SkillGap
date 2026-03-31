from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.config import get_settings
from app.repository import AssessmentRepository
from app.services.assessment import AssessmentEngine
from app.services.catalog import RoleCatalog
from app.services.llm_service import build_llm_service
from app.services.vacancy_matching import VacancyMatchingService
from app.services.vacancy_source import VacancySourceService


API_DESCRIPTION = """
`SkillGap API` помогает:

1. Получить список доступных карьерных ролей.
2. Загрузить анкету для выбранной роли.
3. Отправить ответы пользователя и получить оценку уровня.
4. Посмотреть историю прошлых оценок.
5. Сравнить сохраненную оценку с текстом вакансии или ссылкой на страницу вакансии.

Особенности:

- основная оценка считается детерминированно по матрице компетенций;
- LLM-слой может усиливать extraction из свободного текста и делать human-readable explanation;
- список ролей и логика оценки загружаются из `app/data/*.json`.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "Служебное",
        "description": "Служебные методы для проверки доступности API.",
    },
    {
        "name": "Справочники",
        "description": "Справочные методы: роли, уровни и анкеты по ролям.",
    },
    {
        "name": "Оценка",
        "description": "Создание новой карьерной оценки по ответам пользователя.",
    },
    {
        "name": "История",
        "description": "Просмотр сохраненных оценок конкретного пользователя.",
    },
    {
        "name": "Вакансии",
        "description": "Сравнение сохраненного профиля пользователя с текстом вакансии или URL вакансии.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    catalog = RoleCatalog(settings.data_dir)
    repository = AssessmentRepository(settings.database_url)
    repository.initialize()
    llm_service = build_llm_service(settings)
    vacancy_matching_service = VacancyMatchingService(catalog)
    vacancy_source_service = VacancySourceService()

    app.state.settings = settings
    app.state.catalog = catalog
    app.state.repository = repository
    app.state.engine = AssessmentEngine(catalog)
    app.state.llm_service = llm_service
    app.state.vacancy_matching_service = vacancy_matching_service
    app.state.vacancy_source_service = vacancy_source_service
    yield


app = FastAPI(
    title=get_settings().api_title,
    summary="API карьерного ассистента SkillGap",
    description=API_DESCRIPTION,
    version=get_settings().api_version,
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.include_router(router)


@app.get(
    "/health",
    tags=["Служебное"],
    summary="Проверка доступности API",
    description="Простой health-check. Можно использовать для мониторинга или smoke-проверки сервиса.",
    response_description="Статус доступности API.",
)
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
