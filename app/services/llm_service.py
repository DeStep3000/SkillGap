from __future__ import annotations

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
        model = self.model_config.extraction
        if not model:
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

        try:
            raw_content = self._chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
            )
            extracted = self._parse_profile_json(raw_content, competency_map)
        except Exception as error:  # noqa: BLE001
            logger.warning("OpenRouter extraction failed: %s", error)
            return None

        extracted["source_answers"] = free_text_answers
        extracted["llm_provider"] = "openrouter"
        extracted["llm_model"] = model
        return extracted

    def enhance_assessment(self, result: dict[str, Any]) -> dict[str, Any]:
        model = self.model_config.explanation
        if not model:
            return result

        prompt_payload = {
            "role": result["role_title"],
            "current_level": result["current_level_label"],
            "target_level": result["target_level_label"],
            "total_score": result["total_score"],
            "max_score": result["max_score"],
            "coverage_by_level": result["coverage_by_level"],
            "strengths": result["strengths"],
            "gaps_to_target_level": result["gaps_to_target_level"],
            "gaps_to_next_level": result["gaps_to_next_level"],
            "roadmap": result["roadmap"],
            "project_ideas": result["project_ideas"],
            "summary": result["summary"],
            "structured_profile": result.get("structured_profile"),
            "score_adjustments": result.get("score_adjustments", []),
        }

        system_prompt = (
            "Ты карьерный AI-ассистент для IT-специалистов. "
            "Твоя задача: коротко и понятно объяснить результат оценки уровня. "
            "Не меняй score и уровень, не придумывай новые факты, опирайся только на входные данные. "
            "Ответ дай на русском языке в 1-2 абзацах без markdown."
        )
        user_prompt = (
            "Сформируй понятное human-readable explanation по результату оценки. "
            "Скажи, почему такой уровень, какие сильные стороны уже есть и что важнее всего подтянуть дальше.\n\n"
            f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}"
        )

        try:
            narrative = self._chat(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("OpenRouter explanation failed: %s", error)
            return result

        enriched = dict(result)
        enriched["narrative_explanation"] = narrative
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
        content = raw_content.strip()
        if "```" in content:
            content = content.split("```", maxsplit=1)[-1]
            content = content.rsplit("```", maxsplit=1)[0]
            content = content.replace("json", "", 1).strip()

        if not content.startswith("{"):
            start_index = content.find("{")
            end_index = content.rfind("}")
            if start_index == -1 or end_index == -1:
                raise RuntimeError("No JSON object found in extraction response")
            content = content[start_index : end_index + 1]

        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError("Extraction response is not a JSON object")

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
        content = raw_content.strip()
        if "```" in content:
            content = content.split("```", maxsplit=1)[-1]
            content = content.rsplit("```", maxsplit=1)[0]
            content = content.replace("json", "", 1).strip()

        if not content.startswith("{"):
            start_index = content.find("{")
            end_index = content.rfind("}")
            if start_index == -1 or end_index == -1:
                raise RuntimeError("No JSON object found in vacancy response")
            content = content[start_index : end_index + 1]

        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise RuntimeError("Vacancy response is not a JSON object")

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
            vacancy=settings.openrouter_vacancy_model,
        ),
        app_name=settings.openrouter_app_name,
        site_url=settings.openrouter_site_url,
    )
