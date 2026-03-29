from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RoleSummary(BaseModel):
    id: str
    title: str
    description: str | None = None


class LevelInfo(BaseModel):
    id: str
    label: str


class QuestionOption(BaseModel):
    id: str
    label: str
    description: str | None = None


class QuestionItem(BaseModel):
    id: str
    kind: str
    title: str
    help_text: str | None = None
    options: list[QuestionOption] = Field(default_factory=list)


class QuestionnaireResponse(BaseModel):
    role: RoleSummary
    levels: list[LevelInfo]
    questions: list[QuestionItem]


class AssessmentAnswer(BaseModel):
    question_id: str
    option_id: str | None = None
    text: str | None = None


class AssessmentCreateRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    full_name: str | None = None
    role_id: str
    answers: list[AssessmentAnswer] = Field(default_factory=list)


class CoverageItem(BaseModel):
    level: str
    label: str
    percent: int


class GapItem(BaseModel):
    competency_id: str
    title: str
    current_score: int
    target_score: int
    recommended_action: str
    why_it_matters: str


class RoadmapItem(BaseModel):
    step: int
    focus: str
    action: str


class BreakdownItem(BaseModel):
    competency_id: str
    title: str
    score: int
    max_score: int = 3


class AssessmentResponse(BaseModel):
    assessment_id: int
    role_id: str
    role_title: str
    current_level: str
    current_level_label: str
    target_level: str
    target_level_label: str
    next_level: str | None = None
    next_level_label: str | None = None
    total_score: int
    max_score: int
    coverage_by_level: list[CoverageItem]
    strengths: list[str]
    gaps_to_next_level: list[GapItem]
    gaps_to_target_level: list[GapItem]
    roadmap: list[RoadmapItem]
    project_ideas: list[str]
    reasoning: list[str]
    summary: str
    narrative_explanation: str | None = None
    llm_used: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    structured_profile: dict[str, Any] | None = None
    score_adjustments: list[str] = Field(default_factory=list)
    breakdown: list[BreakdownItem]
    created_at: str | None = None


class AssessmentHistoryItem(BaseModel):
    assessment_id: int
    role_title: str
    current_level: str
    current_level_label: str
    target_level: str
    target_level_label: str
    total_score: int
    max_score: int
    summary: str
    created_at: str


class VacancyMatchRequest(BaseModel):
    assessment_id: int | None = None
    vacancy_text: str


class VacancyRequirementItem(BaseModel):
    skill: str
    normalized_skill: str
    competency_id: str
    competency_title: str
    importance: str
    target_score: int
    match_status: str
    user_score: int


class VacancyMatchResponse(BaseModel):
    vacancy_analysis_id: int
    assessment_id: int
    role_id: str
    role_title: str
    current_level: str
    current_level_label: str
    target_level: str
    target_level_label: str
    match_percent: int
    vacancy_summary: str | None = None
    reasoning: list[str]
    matched_skills: list[str]
    partial_matches: list[str]
    missing_skills: list[str]
    priority_gaps: list[str]
    requirements: list[VacancyRequirementItem]
    llm_used: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    created_at: str | None = None
