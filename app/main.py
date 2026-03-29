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


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    catalog = RoleCatalog(settings.data_dir)
    repository = AssessmentRepository(settings.database_url)
    repository.initialize()
    llm_service = build_llm_service(settings)
    vacancy_matching_service = VacancyMatchingService(catalog)

    app.state.settings = settings
    app.state.catalog = catalog
    app.state.repository = repository
    app.state.engine = AssessmentEngine(catalog)
    app.state.llm_service = llm_service
    app.state.vacancy_matching_service = vacancy_matching_service
    yield


app = FastAPI(
    title=get_settings().api_title,
    version=get_settings().api_version,
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
