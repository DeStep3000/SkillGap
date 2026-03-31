from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request, status

from app.repository import AssessmentRepository
from app.schemas import (
    ApiErrorResponse,
    AssessmentCreateRequest,
    AssessmentHistoryItem,
    AssessmentResponse,
    QuestionnaireResponse,
    RoleSummary,
    VacancyMatchRequest,
    VacancyMatchResponse,
)
from app.services.assessment import AssessmentEngine, AssessmentError
from app.services.catalog import CatalogError, RoleCatalog
from app.services.llm_service import BaseLLMService
from app.services.vacancy_matching import VacancyMatchingService
from app.services.vacancy_source import VacancySourceError, VacancySourceService


router = APIRouter(prefix="/api/v1")

RoleIdPath = Annotated[
    str,
    Path(
        description="Идентификатор роли из справочника, например `python_web_developer` или `ml_engineer`.",
        examples=["python_web_developer"],
    ),
]
TelegramIdPath = Annotated[
    int,
    Path(
        description="Telegram ID пользователя. Используется как ключ для истории оценок.",
        examples=[123456789],
    ),
]
AssessmentIdPath = Annotated[
    int,
    Path(
        description="Идентификатор ранее сохраненной оценки пользователя.",
        examples=[42],
    ),
]
AssessmentRequestBody = Annotated[
    AssessmentCreateRequest,
    Body(
        description=(
            "Тело запроса для расчета новой оценки. "
            "Ответы должны содержать все вопросы анкеты по выбранной роли."
        )
    ),
]
VacancyRequestBody = Annotated[
    VacancyMatchRequest,
    Body(
        description=(
            "Тело запроса для сравнения пользователя с вакансией. "
            "Если `assessment_id` не передан, будет использована последняя оценка пользователя."
        )
    ),
]


def get_catalog(request: Request) -> RoleCatalog:
    return request.app.state.catalog


def get_engine(request: Request) -> AssessmentEngine:
    return request.app.state.engine


def get_repository(request: Request) -> AssessmentRepository:
    return request.app.state.repository


def get_llm_service(request: Request) -> BaseLLMService:
    return request.app.state.llm_service


def get_vacancy_matching_service(request: Request) -> VacancyMatchingService:
    return request.app.state.vacancy_matching_service


def get_vacancy_source_service(request: Request) -> VacancySourceService:
    return request.app.state.vacancy_source_service


@router.get(
    "/reference/roles",
    response_model=list[RoleSummary],
    tags=["Справочники"],
    summary="Получить список доступных ролей",
    description=(
        "Возвращает все роли, доступные в системе. "
        "Используй этот метод первым, чтобы показать пользователю каталог направлений."
    ),
    response_description="Список доступных ролей.",
)
def list_roles(catalog: RoleCatalog = Depends(get_catalog)) -> list[dict]:
    return catalog.list_roles()


@router.get(
    "/reference/roles/{role_id}/questionnaire",
    response_model=QuestionnaireResponse,
    tags=["Справочники"],
    summary="Получить анкету для роли",
    description=(
        "Возвращает анкету для выбранной роли: список уровней, вопросы, типы вопросов "
        "и доступные варианты ответа."
    ),
    response_description="Описание роли и анкета для прохождения оценки.",
    responses={
        404: {
            "model": ApiErrorResponse,
            "description": "Роль с указанным `role_id` не найдена.",
        }
    },
)
def get_questionnaire(
    role_id: RoleIdPath,
    catalog: RoleCatalog = Depends(get_catalog),
) -> dict:
    try:
        return catalog.get_questionnaire(role_id)
    except CatalogError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Оценка"],
    summary="Создать новую оценку пользователя",
    description=(
        "Принимает ответы пользователя по выбранной анкете, рассчитывает уровень, gaps, "
        "roadmap и сохраняет результат в историю. "
        "Если включен LLM-слой, свободный текст может быть дополнительно обработан."
    ),
    response_description="Рассчитанная и сохраненная оценка пользователя.",
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": "Некорректные или неполные ответы анкеты.",
        },
        404: {
            "model": ApiErrorResponse,
            "description": "Роль из запроса не найдена.",
        },
    },
)
def create_assessment(
    payload: AssessmentRequestBody,
    catalog: RoleCatalog = Depends(get_catalog),
    engine: AssessmentEngine = Depends(get_engine),
    repository: AssessmentRepository = Depends(get_repository),
    llm_service: BaseLLMService = Depends(get_llm_service),
) -> dict:
    answers_payload = [item.model_dump() for item in payload.answers]

    try:
        role = catalog.get_role(payload.role_id)
        structured_profile = llm_service.extract_profile(
            role=role,
            answers=answers_payload,
        )
        result = engine.evaluate(
            role_id=payload.role_id,
            answers=answers_payload,
            structured_profile=structured_profile,
        )
    except AssessmentError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except CatalogError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    result = llm_service.enhance_assessment(result)

    assessment_id = repository.save_assessment(
        telegram_id=payload.telegram_id,
        username=payload.username,
        full_name=payload.full_name,
        role_id=payload.role_id,
        answers=answers_payload,
        result=result,
    )

    result["assessment_id"] = assessment_id
    stored = repository.get_assessment(payload.telegram_id, assessment_id)
    result["created_at"] = stored["created_at"] if stored else None
    return result


@router.get(
    "/users/{telegram_id}/history",
    response_model=list[AssessmentHistoryItem],
    tags=["История"],
    summary="Получить историю оценок пользователя",
    description=(
        "Возвращает краткую историю всех сохраненных оценок для конкретного пользователя "
        "по его Telegram ID."
    ),
    response_description="Список прошлых оценок пользователя.",
)
def get_history(
    telegram_id: TelegramIdPath,
    repository: AssessmentRepository = Depends(get_repository),
) -> list[dict]:
    records = repository.list_assessments(telegram_id)
    history = []
    for row in records:
        result = json.loads(row["result_json"])
        history.append(
            {
                "assessment_id": row["id"],
                "role_title": result["role_title"],
                "current_level": row["current_level"],
                "current_level_label": result["current_level_label"],
                "target_level": row["target_level"],
                "target_level_label": result["target_level_label"],
                "total_score": row["total_score"],
                "max_score": row["max_score"],
                "summary": row["summary_text"],
                "created_at": row["created_at"],
            }
        )
    return history


@router.get(
    "/users/{telegram_id}/history/{assessment_id}",
    response_model=AssessmentResponse,
    tags=["История"],
    summary="Получить сохраненную оценку по ID",
    description=(
        "Возвращает полную сохраненную оценку пользователя: breakdown, gaps, roadmap, "
        "объяснение, LLM-метаданные и дату создания."
    ),
    response_description="Полная сохраненная оценка пользователя.",
    responses={
        404: {
            "model": ApiErrorResponse,
            "description": "Оценка не найдена для указанного пользователя.",
        }
    },
)
def get_assessment_detail(
    telegram_id: TelegramIdPath,
    assessment_id: AssessmentIdPath,
    repository: AssessmentRepository = Depends(get_repository),
) -> dict:
    record = repository.get_assessment(telegram_id, assessment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    result = json.loads(record["result_json"])
    result["assessment_id"] = record["id"]
    result["created_at"] = record["created_at"]
    return result


@router.post(
    "/users/{telegram_id}/vacancy-analyses",
    response_model=VacancyMatchResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Вакансии"],
    summary="Сравнить профиль пользователя с вакансией",
    description=(
        "Принимает текст вакансии или ссылку на страницу вакансии, извлекает требования и "
        "сравнивает их с сохраненной оценкой пользователя. Если `assessment_id` не передан, "
        "используется последняя доступная оценка."
    ),
    response_description="Результат vacancy match с приоритетными gaps и найденными совпадениями.",
    responses={
        400: {
            "model": ApiErrorResponse,
            "description": (
                "Пустой текст вакансии, некорректная ссылка или не удалось извлечь "
                "требования из вакансии."
            ),
        },
        404: {
            "model": ApiErrorResponse,
            "description": "Оценка пользователя или роль для этой оценки не найдены.",
        },
    },
)
def create_vacancy_analysis(
    telegram_id: TelegramIdPath,
    payload: VacancyRequestBody,
    catalog: RoleCatalog = Depends(get_catalog),
    repository: AssessmentRepository = Depends(get_repository),
    llm_service: BaseLLMService = Depends(get_llm_service),
    vacancy_matching_service: VacancyMatchingService = Depends(get_vacancy_matching_service),
    vacancy_source_service: VacancySourceService = Depends(get_vacancy_source_service),
) -> dict:
    assessment_record = (
        repository.get_assessment(telegram_id, payload.assessment_id)
        if payload.assessment_id
        else repository.get_latest_assessment(telegram_id)
    )
    if not assessment_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found for vacancy comparison",
        )

    vacancy_source = None
    if payload.vacancy_url:
        try:
            vacancy_source = vacancy_source_service.extract_from_url(payload.vacancy_url)
        except VacancySourceError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            ) from error
        vacancy_text = vacancy_source.vacancy_text
    else:
        vacancy_text = (payload.vacancy_text or "").strip()
        if not vacancy_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vacancy text cannot be empty",
            )

    assessment_result = json.loads(assessment_record["result_json"])
    try:
        role = catalog.get_role(assessment_record["role_id"])
    except CatalogError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    vacancy_profile = llm_service.extract_vacancy(role=role, vacancy_text=vacancy_text)
    if not vacancy_profile or not vacancy_profile.get("requirements"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract vacancy requirements",
        )

    result = vacancy_matching_service.match(
        role_id=assessment_record["role_id"],
        assessment_result=assessment_result,
        vacancy_profile=vacancy_profile,
    )
    result["vacancy_source_url"] = vacancy_source.source_url if vacancy_source else None
    result["vacancy_source_title"] = vacancy_source.source_title if vacancy_source else None
    vacancy_analysis_id, created_at = repository.save_vacancy_analysis(
        assessment_id=int(assessment_record["id"]),
        vacancy_text=vacancy_text,
        extracted_requirements=vacancy_profile,
        result=result,
    )

    result["vacancy_analysis_id"] = vacancy_analysis_id
    result["assessment_id"] = int(assessment_record["id"])
    result["created_at"] = created_at
    return result
