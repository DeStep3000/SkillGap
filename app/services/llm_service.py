from __future__ import annotations

import ast
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OpenRouterModelConfig:
    extraction: str | None
    explanation: str | None
    projects: str | None
    vacancy: str | None


class BaseLLMService:
    def extract_profile(
        self,
        role: dict[str, Any],
        answers: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        return None

    def enhance_assessment(self, result: dict[str, Any]) -> dict[str, Any]:
        return result

    def extract_vacancy(
        self,
        role: dict[str, Any],
        vacancy_text: str,
    ) -> dict[str, Any] | None:
        return None


class DisabledLLMService(BaseLLMService):
    pass


class OpenRouterLLMService(BaseLLMService):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        model_config: OpenRouterModelConfig,
        app_name: str,
        site_url: str | None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.model_config = model_config
        self.app_name = app_name
        self.site_url = site_url

    def extract_profile(
        self,
        role: dict[str, Any],
        answers: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        candidate_models = self._candidate_models(
            self.model_config.extraction,
            self.model_config.explanation,
            self.model_config.projects,
            self.model_config.vacancy,
        )
        if not candidate_models:
            return None

        free_text_answers = self._collect_free_text_answers(role, answers)
        if not free_text_answers:
            return None

        competency_map = {
            item["id"]: item["title"] for item in role.get("competencies", [])
        }
        system_prompt = (
            "Ты извлекаешь структурированный профиль IT-специалиста из свободного текста. "
            "Верни только JSON без markdown и без пояснений. "
            "Не выдумывай факты. Если данных не хватает, оставляй пустой список или 0."
        )
        user_prompt = (
            "На основе ответов пользователя собери JSON со структурой:\n"
            "{\n"
            '  "normalized_skills": ["skill"],\n'
            '  "strengths": ["..."],\n'
            '  "weaknesses": ["..."],\n'
            '  "task_types": ["..."],\n'
            '  "summary": "короткое резюме",\n'
            '  "suggested_scores": {"competency_id": 0}\n'
            "}\n\n"
            "Используй только эти competency_id для suggested_scores:\n"
            f"{json.dumps(competency_map, ensure_ascii=False, indent=2)}\n\n"
            "Ответы пользователя:\n"
            f"{json.dumps(free_text_answers, ensure_ascii=False, indent=2)}"
        )

        for index, model in enumerate(candidate_models):
            try:
                raw_content = self._chat(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.1,
                )
                extracted = self._parse_profile_json(raw_content, competency_map)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "OpenRouter extraction failed for model %s: %s",
                    model,
                    error,
                )
                continue

            if index > 0:
                logger.info(
                    "OpenRouter extraction fell back to model %s after previous model failure",
                    model,
                )
            extracted["source_answers"] = free_text_answers
            extracted["llm_provider"] = "openrouter"
            extracted["llm_model"] = model
            return extracted

        return None

    def enhance_assessment(self, result: dict[str, Any]) -> dict[str, Any]:
        enrichment_models = self._candidate_models(
            self.model_config.explanation,
            self.model_config.projects,
            self.model_config.extraction,
        )
        if not enrichment_models:
            return result

        enrichment, model = self._generate_assessment_enrichment(
            result,
            enrichment_models,
        )
        if not enrichment or not model:
            return result

        enriched = dict(result)
        if enrichment.get("project_ideas"):
            enriched["project_ideas"] = enrichment["project_ideas"]
        if enrichment.get("narrative_explanation"):
            enriched["narrative_explanation"] = enrichment["narrative_explanation"]
        enriched["llm_used"] = True
        enriched["llm_provider"] = "openrouter"
        enriched["llm_model"] = model
        return enriched

    def extract_vacancy(
        self,
        role: dict[str, Any],
        vacancy_text: str,
    ) -> dict[str, Any] | None:
        candidate_models = self._candidate_models(
            self.model_config.vacancy,
            self.model_config.extraction,
        )
        if not candidate_models:
            return None

        competency_map = {
            item["id"]: item["title"] for item in role.get("competencies", [])
        }
        system_prompt = (
            "Ты извлекаешь требования вакансии для IT-специалиста. "
            "Верни только JSON без markdown и без пояснений. "
            "Не выдумывай лишние требования и используй только данные из текста вакансии."
        )
        user_prompt = (
            "На основе текста вакансии верни JSON со структурой:\n"
            "{\n"
            '  "summary": "короткое резюме вакансии",\n'
            '  "requirements": [\n'
            "    {\n"
            '      "skill": "FastAPI",\n'
            '      "normalized_skill": "fastapi",\n'
            '      "competency_id": "web_frameworks",\n'
            '      "importance": "high",\n'
            '      "target_score": 2\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Используй только эти competency_id:\n"
            f"{json.dumps(competency_map, ensure_ascii=False, indent=2)}\n\n"
            "Текст вакансии:\n"
            f"{vacancy_text}"
        )

        for index, model in enumerate(candidate_models):
            try:
                raw_content = self._chat(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.1,
                )
                parsed = self._parse_vacancy_json(raw_content, competency_map)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "OpenRouter vacancy extraction failed for model %s: %s",
                    model,
                    error,
                )
                continue

            if index > 0:
                logger.info(
                    "OpenRouter vacancy extraction fell back to model %s after previous model failure",
                    model,
                )
            parsed["llm_provider"] = "openrouter"
            parsed["llm_model"] = model
            return parsed

        return None

    def _chat(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RuntimeError(self._format_http_error(error, model)) from error
        except httpx.HTTPError as error:
            raise RuntimeError(f"OpenRouter request failed for model {model}: {error}") from error

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("Unexpected OpenRouter response format") from error

        if isinstance(content, list):
            text_chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
            content = "\n".join(chunk for chunk in text_chunks if chunk)

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("OpenRouter returned empty content")

        return content.strip()

    def _generate_assessment_enrichment(
        self,
        result: dict[str, Any],
        candidate_models: list[str],
    ) -> tuple[dict[str, Any] | None, str | None]:
        if not candidate_models:
            return None, None

        prompt_payload = {
            "role": result["role_title"],
            "current_level": result["current_level_label"],
            "target_level": result["target_level_label"],
            "total_score": result["total_score"],
            "max_score": result["max_score"],
            "coverage_by_level": result["coverage_by_level"],
            "next_level": result.get("next_level_label"),
            "strengths": result.get("strengths", []),
            "gaps_to_target_level": result.get("gaps_to_target_level", []),
            "gaps_to_next_level": result.get("gaps_to_next_level", []),
            "roadmap": result.get("roadmap", []),
            "structured_profile": result.get("structured_profile"),
            "breakdown": result.get("breakdown", []),
            "summary": result.get("summary"),
            "score_adjustments": result.get("score_adjustments", []),
        }
        system_prompt = (
            "Ты карьерный AI-ассистент для IT-специалистов. "
            "Верни только JSON без markdown и без пояснений. "
            "Нужно сделать две вещи сразу: "
            "1) коротко объяснить результат оценки уровня; "
            "2) предложить 2 portfolio-проекта под сильные стороны и gaps пользователя. "
            "Не меняй score и уровень, не придумывай новые факты, опирайся только на входные данные."
        )
        user_prompt = (
            "Сформируй JSON вида:\n"
            "{\n"
            '  "narrative_explanation": "1-2 абзаца на русском без markdown",\n'
            '  "project_ideas": [\n'
            '    "Идея 1...",\n'
            '    "Идея 2..."\n'
            "  ]\n"
            "}\n\n"
            "Требования к project_ideas: "
            "каждая идея должна быть 1-2 предложения и включать, "
            "что это за проект, какой стек/инструменты использовать, "
            "какие навыки он демонстрирует и какой gap помогает закрыть.\n\n"
            "Входные данные:\n"
            f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
        )

        for index, model in enumerate(candidate_models):
            try:
                raw_content = self._chat(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.4,
                )
                enrichment = self._parse_assessment_enrichment_json(raw_content)
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "OpenRouter assessment enrichment failed for model %s: %s",
                    model,
                    error,
                )
                continue

            if index > 0:
                logger.info(
                    "OpenRouter assessment enrichment fell back to model %s after previous model failure",
                    model,
                )
            return enrichment, model

        return None, None

    @staticmethod
    def _candidate_models(*models: str | None) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for model in models:
            if not model:
                continue
            normalized = model.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _format_http_error(error: httpx.HTTPStatusError, model: str) -> str:
        response = error.response
        detail = OpenRouterLLMService._extract_error_detail(response)
        if detail:
            return (
                f"OpenRouter request failed for model {model} with "
                f"HTTP {response.status_code}: {detail}"
            )
        return (
            f"OpenRouter request failed for model {model} with "
            f"HTTP {response.status_code}"
        )

    @staticmethod
    def _extract_error_detail(response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error_payload = payload.get("error")
            if isinstance(error_payload, dict):
                message = error_payload.get("message")
                if isinstance(message, str) and message.strip():
                    return message.strip()
            if isinstance(error_payload, str) and error_payload.strip():
                return error_payload.strip()

            for key in ("message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        text_body = response.text.strip()
        if not text_body:
            return None
        compact_body = " ".join(text_body.split())
        if response.status_code == 404 and "<html" in compact_body.lower():
            return "received an HTML 404 page from OpenRouter"
        return compact_body[:300]

    @staticmethod
    def _collect_free_text_answers(
        role: dict[str, Any],
        answers: list[dict[str, Any]],
    ) -> dict[str, str]:
        question_map = {question["id"]: question for question in role.get("questions", [])}
        free_text_answers: dict[str, str] = {}

        for answer in answers:
            question = question_map.get(answer["question_id"])
            if not question or question.get("kind") != "free_text":
                continue
            text_value = (answer.get("text") or "").strip()
            if text_value:
                free_text_answers[answer["question_id"]] = text_value

        return free_text_answers

    @staticmethod
    def _parse_profile_json(
        raw_content: str,
        competency_map: dict[str, str],
    ) -> dict[str, Any]:
        payload = OpenRouterLLMService._load_json_object(
            raw_content,
            context="extraction",
        )

        normalized_skills = payload.get("normalized_skills", [])
        strengths = payload.get("strengths", [])
        weaknesses = payload.get("weaknesses", [])
        task_types = payload.get("task_types", [])
        suggested_scores = payload.get("suggested_scores", {})

        cleaned_scores: dict[str, int] = {}
        if isinstance(suggested_scores, dict):
            for competency_id, raw_score in suggested_scores.items():
                if competency_id not in competency_map:
                    continue
                try:
                    cleaned_scores[competency_id] = max(0, min(3, int(raw_score)))
                except (TypeError, ValueError):
                    continue

        return {
            "normalized_skills": [str(item) for item in normalized_skills][:12]
            if isinstance(normalized_skills, list)
            else [],
            "strengths": [str(item) for item in strengths][:8]
            if isinstance(strengths, list)
            else [],
            "weaknesses": [str(item) for item in weaknesses][:8]
            if isinstance(weaknesses, list)
            else [],
            "task_types": [str(item) for item in task_types][:8]
            if isinstance(task_types, list)
            else [],
            "summary": str(payload.get("summary", ""))[:500],
            "suggested_scores": cleaned_scores,
        }

    @staticmethod
    def _parse_vacancy_json(
        raw_content: str,
        competency_map: dict[str, str],
    ) -> dict[str, Any]:
        payload = OpenRouterLLMService._load_json_object(
            raw_content,
            context="vacancy",
        )

        requirements = payload.get("requirements", [])
        cleaned_requirements: list[dict[str, Any]] = []
        if isinstance(requirements, list):
            for item in requirements:
                if not isinstance(item, dict):
                    continue
                competency_id = str(item.get("competency_id", "")).strip()
                if competency_id not in competency_map:
                    continue
                importance = str(item.get("importance", "medium")).strip().lower()
                if importance not in {"high", "medium", "low"}:
                    importance = "medium"
                try:
                    target_score = max(1, min(3, int(item.get("target_score", 1))))
                except (TypeError, ValueError):
                    target_score = 1

                skill = str(item.get("skill", "")).strip() or competency_map[competency_id]
                normalized_skill = (
                    str(item.get("normalized_skill", "")).strip().lower() or skill.lower()
                )
                cleaned_requirements.append(
                    {
                        "skill": skill,
                        "normalized_skill": normalized_skill,
                        "competency_id": competency_id,
                        "importance": importance,
                        "target_score": target_score,
                    }
                )

        return {
            "summary": str(payload.get("summary", ""))[:500],
            "requirements": cleaned_requirements,
        }

    @staticmethod
    def _parse_assessment_enrichment_json(raw_content: str) -> dict[str, Any]:
        payload = OpenRouterLLMService._load_json_object(
            raw_content,
            context="assessment enrichment",
        )

        raw_project_ideas = payload.get("project_ideas", [])
        cleaned_project_ideas: list[str] = []
        if isinstance(raw_project_ideas, list):
            seen: set[str] = set()
            for item in raw_project_ideas:
                text = " ".join(str(item).split()).strip(" -•")
                if not text:
                    continue
                lowered = text.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                cleaned_project_ideas.append(text[:500])
                if len(cleaned_project_ideas) == 2:
                    break

        narrative = " ".join(str(payload.get("narrative_explanation", "")).split()).strip()
        if not narrative and not cleaned_project_ideas:
            raise RuntimeError("Assessment enrichment response is empty")

        return {
            "narrative_explanation": narrative or None,
            "project_ideas": cleaned_project_ideas,
        }

    @staticmethod
    def _load_json_object(raw_content: str, *, context: str) -> dict[str, Any]:
        content = OpenRouterLLMService._extract_json_object_text(
            raw_content,
            context=context,
        )
        attempts = [
            content,
            OpenRouterLLMService._normalize_json_like_content(content),
        ]

        for attempt in attempts:
            if not attempt:
                continue
            try:
                payload = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
            raise RuntimeError(f"{context.capitalize()} response is not a JSON object")

        python_like = OpenRouterLLMService._to_python_literal(attempts[-1] or content)
        try:
            payload = ast.literal_eval(python_like)
        except (SyntaxError, ValueError) as error:
            raise RuntimeError(f"Invalid {context} response: {error}") from error

        if not isinstance(payload, dict):
            raise RuntimeError(f"{context.capitalize()} response is not a JSON object")
        return payload

    @staticmethod
    def _extract_json_object_text(raw_content: str, *, context: str) -> str:
        content = raw_content.strip()
        if "```" in content:
            content = content.split("```", maxsplit=1)[-1]
            content = content.rsplit("```", maxsplit=1)[0]
            content = content.replace("json", "", 1).strip()

        if content.startswith("{"):
            return content

        start_index = content.find("{")
        end_index = content.rfind("}")
        if start_index == -1 or end_index == -1:
            raise RuntimeError(f"No JSON object found in {context} response")
        return content[start_index : end_index + 1]

    @staticmethod
    def _normalize_json_like_content(content: str) -> str:
        normalized = (
            content.replace("\ufeff", "")
            .replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
        )
        return normalized.replace(",]", "]").replace(",}", "}")

    @staticmethod
    def _to_python_literal(content: str) -> str:
        result: list[str] = []
        index = 0
        in_string = False
        quote_char = ""

        while index < len(content):
            char = content[index]

            if in_string:
                result.append(char)
                if char == "\\" and index + 1 < len(content):
                    index += 1
                    result.append(content[index])
                elif char == quote_char:
                    in_string = False
                index += 1
                continue

            if char in {'"', "'"}:
                in_string = True
                quote_char = char
                result.append(char)
                index += 1
                continue

            matched = OpenRouterLLMService._replace_json_literal_token(content, index)
            if matched is not None:
                replacement, width = matched
                result.append(replacement)
                index += width
                continue

            result.append(char)
            index += 1

        return "".join(result)

    @staticmethod
    def _replace_json_literal_token(content: str, index: int) -> tuple[str, int] | None:
        token_map = {
            "true": "True",
            "false": "False",
            "null": "None",
        }
        for token, replacement in token_map.items():
            if not content.startswith(token, index):
                continue

            left_ok = index == 0 or not (
                content[index - 1].isalnum() or content[index - 1] == "_"
            )
            right_index = index + len(token)
            right_ok = right_index >= len(content) or not (
                content[right_index].isalnum() or content[right_index] == "_"
            )
            if left_ok and right_ok:
                return replacement, len(token)

        return None


def build_llm_service(settings: Any) -> BaseLLMService:
    provider = (settings.llm_provider or "").lower()
    if provider != "openrouter":
        return DisabledLLMService()

    if not settings.openrouter_api_key:
        logger.warning("LLM provider is openrouter but OPENROUTER_API_KEY is empty")
        return DisabledLLMService()

    return OpenRouterLLMService(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        model_config=OpenRouterModelConfig(
            extraction=settings.openrouter_extraction_model,
            explanation=settings.openrouter_explanation_model,
            projects=settings.openrouter_projects_model,
            vacancy=settings.openrouter_vacancy_model,
        ),
        app_name=settings.openrouter_app_name,
        site_url=settings.openrouter_site_url,
    )
