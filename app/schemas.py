from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RoleSummary(BaseModel):
    id: str = Field(
        description="Стабильный идентификатор роли, который используется в API и JSON-матрицах.",
        examples=["python_web_developer"],
    )
    title: str = Field(
        description="Человекочитаемое название роли.",
        examples=["Python Web Developer"],
    )
    description: str | None = Field(
        default=None,
        description="Краткое описание роли.",
        examples=["Оценка backend/web-разработчика на Python."],
    )


class LevelInfo(BaseModel):
    id: str = Field(
        description="Стабильный идентификатор уровня.",
        examples=["middle"],
    )
    label: str = Field(
        description="Название уровня, которое показывается пользователю.",
        examples=["Middle"],
    )


class QuestionOption(BaseModel):
    id: str = Field(
        description="Идентификатор варианта ответа.",
        examples=["target_middle"],
    )
    label: str = Field(
        description="Текст варианта ответа, который видит пользователь.",
        examples=["Middle"],
    )
    description: str | None = Field(
        default=None,
        description="Дополнительное пояснение к варианту ответа.",
        examples=["Хочу самостоятельно вести фичи и быть сильнее в backend."],
    )


class QuestionItem(BaseModel):
    id: str = Field(
        description="Стабильный идентификатор вопроса.",
        examples=["backend_foundation"],
    )
    kind: str = Field(
        description="Тип вопроса: `meta`, `competency` или `free_text`.",
        examples=["competency"],
    )
    title: str = Field(
        description="Основной текст вопроса.",
        examples=["Какой у тебя сейчас уровень backend-базы на Python?"],
    )
    help_text: str | None = Field(
        default=None,
        description="Дополнительная подсказка к вопросу.",
        examples=["Смотри на практику, а не только на теорию."],
    )
    options: list[QuestionOption] = Field(
        default_factory=list,
        description="Доступные варианты ответа. Для `free_text` обычно пустой список.",
    )


class QuestionnaireResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "role": {
                    "id": "python_web_developer",
                    "title": "Python Web Developer",
                    "description": "Оценка backend/web-разработчика на Python.",
                },
                "levels": [
                    {"id": "junior", "label": "Junior"},
                    {"id": "middle", "label": "Middle"},
                    {"id": "senior", "label": "Senior"},
                ],
                "questions": [
                    {
                        "id": "target_level",
                        "kind": "meta",
                        "title": "К какому уровню ты хочешь прийти в ближайшей перспективе?",
                        "help_text": "Это поможет показать приоритетные gaps именно до твоей цели.",
                        "options": [
                            {
                                "id": "target_middle",
                                "label": "Middle",
                                "description": "Хочу самостоятельно вести фичи и быть сильнее в backend.",
                            }
                        ],
                    }
                ],
            }
        }
    )

    role: RoleSummary = Field(description="Информация о выбранной роли.")
    levels: list[LevelInfo] = Field(description="Список уровней, используемых в этой роли.")
    questions: list[QuestionItem] = Field(description="Анкета, которую нужно показать пользователю.")


class AssessmentAnswer(BaseModel):
    question_id: str = Field(
        description="Идентификатор вопроса, на который дается ответ.",
        examples=["target_level"],
    )
    option_id: str | None = Field(
        default=None,
        description=(
            "Идентификатор выбранного варианта ответа. "
            "Используется для вопросов типов `meta` и `competency`."
        ),
        examples=["target_middle"],
    )
    text: str | None = Field(
        default=None,
        description="Текстовый ответ пользователя. Используется для вопросов типа `free_text`.",
        examples=["Работал с FastAPI, PostgreSQL, pytest и Docker, вел API-фичи end-to-end."],
    )


class AssessmentCreateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "telegram_id": 123456789,
                "username": "skillgap_user",
                "full_name": "Ivan Ivanov",
                "role_id": "python_web_developer",
                "answers": [
                    {"question_id": "target_level", "option_id": "target_middle"},
                    {
                        "question_id": "experience_summary",
                        "text": "Работал с FastAPI, PostgreSQL, pytest и Docker, вел API-фичи end-to-end.",
                    },
                    {
                        "question_id": "backend_foundation",
                        "option_id": "backend_foundation_2",
                    },
                    {
                        "question_id": "delivery_quality",
                        "option_id": "delivery_quality_2",
                    },
                    {
                        "question_id": "ownership_collaboration",
                        "option_id": "ownership_collaboration_2",
                    },
                ],
            }
        }
    )

    telegram_id: int = Field(
        description="Telegram ID пользователя, под которым будет сохранена оценка.",
        examples=[123456789],
    )
    username: str | None = Field(
        default=None,
        description="Username пользователя в Telegram, если доступен.",
        examples=["skillgap_user"],
    )
    full_name: str | None = Field(
        default=None,
        description="Полное имя пользователя, если доступно.",
        examples=["Ivan Ivanov"],
    )
    role_id: str = Field(
        description="Идентификатор роли, по которой создается оценка.",
        examples=["python_web_developer"],
    )
    answers: list[AssessmentAnswer] = Field(
        default_factory=list,
        description="Полный набор ответов пользователя на анкету выбранной роли.",
    )


class CoverageItem(BaseModel):
    level: str = Field(description="Идентификатор уровня.", examples=["middle"])
    label: str = Field(description="Название уровня.", examples=["Middle"])
    percent: int = Field(description="Процент покрытия матрицы для этого уровня.", examples=[72])


class GapItem(BaseModel):
    competency_id: str = Field(description="Идентификатор компетенции.", examples=["testing"])
    title: str = Field(description="Название компетенции.", examples=["Тестирование"])
    current_score: int = Field(description="Текущий балл пользователя по компетенции.", examples=[1])
    target_score: int = Field(description="Целевой балл для уровня или вакансии.", examples=[2])
    recommended_action: str = Field(
        description="Практическая рекомендация, что делать для роста.",
        examples=["Добавь pytest, unit и integration тесты, фикстуры и проверки основных сценариев API."],
    )
    why_it_matters: str = Field(
        description="Краткое объяснение, почему эта компетенция важна.",
        examples=["Без тестов сложно расти в сторону надежной разработки и уверенно выпускать изменения."],
    )


class RoadmapItem(BaseModel):
    step: int = Field(description="Порядковый номер шага в roadmap.", examples=[1])
    focus: str = Field(description="Фокус этого шага развития.", examples=["Тестирование"])
    action: str = Field(
        description="Конкретное действие, которое рекомендуется сделать.",
        examples=["Добавь unit и integration тесты для ключевых сценариев API."],
    )


class BreakdownItem(BaseModel):
    competency_id: str = Field(description="Идентификатор компетенции.", examples=["python_core"])
    title: str = Field(description="Название компетенции.", examples=["Python core"])
    score: int = Field(description="Итоговый балл пользователя по этой компетенции.", examples=[2])
    max_score: int = Field(default=3, description="Максимально возможный балл по компетенции.", examples=[3])


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": 42,
                "role_id": "python_web_developer",
                "role_title": "Python Web Developer",
                "current_level": "middle",
                "current_level_label": "Middle",
                "target_level": "middle",
                "target_level_label": "Middle",
                "next_level": "senior",
                "next_level_label": "Senior",
                "total_score": 19,
                "max_score": 30,
                "coverage_by_level": [
                    {"level": "junior", "label": "Junior", "percent": 100},
                    {"level": "middle", "label": "Middle", "percent": 76},
                    {"level": "senior", "label": "Senior", "percent": 44},
                ],
                "strengths": ["Python core", "FastAPI/Django и REST API"],
                "gaps_to_next_level": [],
                "gaps_to_target_level": [
                    {
                        "competency_id": "testing",
                        "title": "Тестирование",
                        "current_score": 1,
                        "target_score": 2,
                        "recommended_action": "Добавь pytest, unit и integration тесты.",
                        "why_it_matters": "Без тестов сложно уверенно выпускать изменения.",
                    }
                ],
                "roadmap": [
                    {
                        "step": 1,
                        "focus": "Тестирование",
                        "action": "Добавь unit и integration тесты для ключевых сценариев.",
                    }
                ],
                "project_ideas": ["Task Tracker API с FastAPI, PostgreSQL, Docker Compose, pytest и CI-пайплайном."],
                "reasoning": ["Суммарный балл: 19 из 30. Покрытие уровня Middle: 76%."],
                "summary": "Сейчас твой профиль ближе всего к уровню Middle.",
                "narrative_explanation": "У тебя уже есть хорошая база по backend-разработке, но для более уверенного Middle стоит усилить testing и production practices.",
                "llm_used": True,
                "llm_provider": "openrouter",
                "llm_model": "anthropic/claude-sonnet-4.6",
                "structured_profile": {
                    "normalized_skills": ["fastapi", "postgresql", "pytest"],
                    "strengths": ["backend-разработка", "API"],
                    "weaknesses": ["тестирование"],
                    "task_types": ["crud", "api"],
                    "summary": "Профиль backend-разработчика с опытом API и БД.",
                    "suggested_scores": {"testing": 2},
                },
                "score_adjustments": ["Тестирование: 1 → 2"],
                "breakdown": [
                    {
                        "competency_id": "python_core",
                        "title": "Python core",
                        "score": 2,
                        "max_score": 3,
                    }
                ],
                "created_at": "2026-03-30T12:34:56",
            }
        }
    )

    assessment_id: int = Field(description="Идентификатор сохраненной оценки.", examples=[42])
    role_id: str = Field(description="Идентификатор роли.", examples=["python_web_developer"])
    role_title: str = Field(description="Название роли.", examples=["Python Web Developer"])
    current_level: str = Field(description="Рассчитанный текущий уровень пользователя.", examples=["middle"])
    current_level_label: str = Field(description="Человекочитаемое название текущего уровня.", examples=["Middle"])
    target_level: str = Field(description="Целевой уровень из анкеты.", examples=["senior"])
    target_level_label: str = Field(description="Человекочитаемое название целевого уровня.", examples=["Senior"])
    next_level: str | None = Field(
        default=None,
        description="Следующий уровень после текущего, если он существует.",
        examples=["senior"],
    )
    next_level_label: str | None = Field(
        default=None,
        description="Человекочитаемое название следующего уровня.",
        examples=["Senior"],
    )
    total_score: int = Field(description="Суммарный балл пользователя по матрице.", examples=[19])
    max_score: int = Field(description="Максимально возможный суммарный балл.", examples=[30])
    coverage_by_level: list[CoverageItem] = Field(
        description="Покрытие матрицы по каждому уровню в процентах."
    )
    strengths: list[str] = Field(description="Сильные стороны пользователя по результатам оценки.")
    gaps_to_next_level: list[GapItem] = Field(
        description="Компетенции, которые стоит подтянуть до следующего уровня."
    )
    gaps_to_target_level: list[GapItem] = Field(
        description="Компетенции, которые важнее всего усилить до выбранной цели."
    )
    roadmap: list[RoadmapItem] = Field(description="Приоритетный roadmap развития на основе gaps.")
    project_ideas: list[str] = Field(description="Мини-проекты, которые помогут расти в выбранной роли.")
    reasoning: list[str] = Field(description="Краткие объяснения, почему система поставила такой результат.")
    summary: str = Field(description="Короткое текстовое резюме по итогам оценки.")
    narrative_explanation: str | None = Field(
        default=None,
        description="Human-readable explanation от LLM, если такой слой включен.",
    )
    llm_used: bool = Field(
        default=False,
        description="Флаг, что в финальном ответе использовался LLM-слой.",
    )
    llm_provider: str | None = Field(
        default=None,
        description="Название провайдера LLM, если использовался.",
        examples=["openrouter"],
    )
    llm_model: str | None = Field(
        default=None,
        description="Идентификатор модели LLM, если использовалась.",
        examples=["anthropic/claude-sonnet-4.6"],
    )
    structured_profile: dict[str, Any] | None = Field(
        default=None,
        description="Структурированный профиль, извлеченный из свободного текста пользователя.",
    )
    score_adjustments: list[str] = Field(
        default_factory=list,
        description="Какие корректировки итоговых баллов были внесены на основе extraction из free-text.",
    )
    breakdown: list[BreakdownItem] = Field(
        description="Итоговый breakdown баллов по всем компетенциям роли."
    )
    created_at: str | None = Field(
        default=None,
        description="Дата и время создания оценки в формате ISO.",
        examples=["2026-03-30T12:34:56"],
    )


class AssessmentHistoryItem(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": 42,
                "role_title": "Python Web Developer",
                "current_level": "middle",
                "current_level_label": "Middle",
                "target_level": "senior",
                "target_level_label": "Senior",
                "total_score": 19,
                "max_score": 30,
                "summary": "Сейчас твой профиль ближе всего к уровню Middle.",
                "created_at": "2026-03-30T12:34:56",
            }
        }
    )

    assessment_id: int = Field(description="Идентификатор оценки.", examples=[42])
    role_title: str = Field(description="Название роли, по которой была оценка.", examples=["Python Web Developer"])
    current_level: str = Field(description="Идентификатор текущего уровня.", examples=["middle"])
    current_level_label: str = Field(description="Название текущего уровня.", examples=["Middle"])
    target_level: str = Field(description="Идентификатор целевого уровня.", examples=["senior"])
    target_level_label: str = Field(description="Название целевого уровня.", examples=["Senior"])
    total_score: int = Field(description="Суммарный балл по матрице.", examples=[19])
    max_score: int = Field(description="Максимальный суммарный балл.", examples=[30])
    summary: str = Field(description="Краткое резюме результата оценки.")
    created_at: str = Field(description="Дата и время создания оценки в формате ISO.", examples=["2026-03-30T12:34:56"])


class VacancyMatchRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "assessment_id": 42,
                "vacancy_url": "https://example.com/jobs/python-backend-developer",
            }
        }
    )

    assessment_id: int | None = Field(
        default=None,
        description="Идентификатор оценки, с которой нужно сравнить вакансию. Если не передан, будет взята последняя оценка пользователя.",
        examples=[42],
    )
    vacancy_text: str | None = Field(
        default=None,
        description="Полный текст вакансии в свободной форме. Можно передать вместо `vacancy_url` для обратной совместимости.",
        examples=["Ищем Python Backend Developer с опытом FastAPI, PostgreSQL, Docker, CI/CD и тестирования."],
    )
    vacancy_url: str | None = Field(
        default=None,
        description="Ссылка на страницу вакансии. Backend загрузит страницу, извлечет текст и только потом выполнит vacancy matching.",
        examples=["https://example.com/jobs/python-backend-developer"],
    )

    @field_validator("vacancy_text", "vacancy_url", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode="after")
    def _validate_source(self) -> "VacancyMatchRequest":
        has_text = bool(self.vacancy_text)
        has_url = bool(self.vacancy_url)
        if has_text == has_url:
            raise ValueError("Provide exactly one of vacancy_text or vacancy_url")
        return self


class VacancyRequirementItem(BaseModel):
    skill: str = Field(description="Навык или требование, выделенное из вакансии.", examples=["FastAPI"])
    normalized_skill: str = Field(description="Нормализованное имя навыка для внутреннего сравнения.", examples=["fastapi"])
    competency_id: str = Field(description="Компетенция матрицы, к которой отнесен навык.", examples=["web_frameworks"])
    competency_title: str = Field(description="Человекочитаемое название компетенции.", examples=["FastAPI/Django и REST API"])
    importance: str = Field(description="Важность требования: `high`, `medium` или `low`.", examples=["high"])
    target_score: int = Field(description="Какой балл по компетенции нужен для этого требования.", examples=[2])
    match_status: str = Field(description="Статус совпадения: `matched`, `partial` или `missing`.", examples=["partial"])
    user_score: int = Field(description="Текущий балл пользователя по этой компетенции.", examples=[1])


class VacancyMatchResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vacancy_analysis_id": 7,
                "assessment_id": 42,
                "role_id": "python_web_developer",
                "role_title": "Python Web Developer",
                "current_level": "middle",
                "current_level_label": "Middle",
                "target_level": "senior",
                "target_level_label": "Senior",
                "match_percent": 67,
                "vacancy_summary": "Вакансия для backend-разработчика с акцентом на API, БД и production delivery.",
                "vacancy_source_url": "https://example.com/jobs/python-backend-developer",
                "vacancy_source_title": "Python Backend Developer",
                "reasoning": [
                    "Match с вакансией: 67%.",
                    "Совпадений: 4, частичных совпадений: 2, пробелов: 1."
                ],
                "matched_skills": ["FastAPI", "PostgreSQL"],
                "partial_matches": ["Docker"],
                "missing_skills": ["CI/CD"],
                "priority_gaps": ["CI/CD", "Тестирование"],
                "requirements": [
                    {
                        "skill": "FastAPI",
                        "normalized_skill": "fastapi",
                        "competency_id": "web_frameworks",
                        "competency_title": "FastAPI/Django и REST API",
                        "importance": "high",
                        "target_score": 2,
                        "match_status": "matched",
                        "user_score": 2
                    }
                ],
                "llm_used": True,
                "llm_provider": "openrouter",
                "llm_model": "openai/gpt-5.4",
                "created_at": "2026-03-30T12:45:10"
            }
        }
    )

    vacancy_analysis_id: int = Field(description="Идентификатор сохраненного анализа вакансии.", examples=[7])
    assessment_id: int = Field(description="Идентификатор оценки, с которой сравнивали вакансию.", examples=[42])
    role_id: str = Field(description="Идентификатор роли.", examples=["python_web_developer"])
    role_title: str = Field(description="Название роли.", examples=["Python Web Developer"])
    current_level: str = Field(description="Текущий уровень пользователя из оценки.", examples=["middle"])
    current_level_label: str = Field(description="Название текущего уровня пользователя.", examples=["Middle"])
    target_level: str = Field(description="Целевой уровень пользователя из оценки.", examples=["senior"])
    target_level_label: str = Field(description="Название целевого уровня пользователя.", examples=["Senior"])
    match_percent: int = Field(description="Процент совпадения пользователя с вакансией.", examples=[67])
    vacancy_summary: str | None = Field(
        default=None,
        description="Короткое резюме вакансии после extraction.",
    )
    vacancy_source_url: str | None = Field(
        default=None,
        description="Ссылка на исходную страницу вакансии, если анализ запускался по URL.",
        examples=["https://example.com/jobs/python-backend-developer"],
    )
    vacancy_source_title: str | None = Field(
        default=None,
        description="Заголовок страницы вакансии, который удалось извлечь перед анализом.",
        examples=["Python Backend Developer"],
    )
    reasoning: list[str] = Field(description="Краткие объяснения, почему match получился именно таким.")
    matched_skills: list[str] = Field(description="Навыки, которые уже хорошо совпадают с вакансией.")
    partial_matches: list[str] = Field(description="Навыки, которые совпадают частично.")
    missing_skills: list[str] = Field(description="Навыки и требования, которых пока не хватает.")
    priority_gaps: list[str] = Field(description="Самые приоритетные пробелы, которые стоит закрывать в первую очередь.")
    requirements: list[VacancyRequirementItem] = Field(
        description="Нормализованный список требований вакансии после extraction и сопоставления."
    )
    llm_used: bool = Field(default=False, description="Флаг, что для анализа вакансии использовался LLM.")
    llm_provider: str | None = Field(
        default=None,
        description="Провайдер LLM, если extraction вакансии был выполнен.",
        examples=["openrouter"],
    )
    llm_model: str | None = Field(
        default=None,
        description="Модель LLM, использованная для extraction вакансии.",
        examples=["openai/gpt-5.4"],
    )
    created_at: str | None = Field(
        default=None,
        description="Дата и время создания анализа вакансии в формате ISO.",
        examples=["2026-03-30T12:45:10"],
    )


class ApiErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Could not extract vacancy requirements",
            }
        }
    )

    detail: str = Field(
        description="Текстовое описание ошибки, которое можно показать пользователю или использовать в логике клиента."
    )
