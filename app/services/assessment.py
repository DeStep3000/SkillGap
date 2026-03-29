from __future__ import annotations

from typing import Any

from app.services.catalog import RoleCatalog


class AssessmentError(ValueError):
    pass


class AssessmentEngine:
    def __init__(self, catalog: RoleCatalog) -> None:
        self.catalog = catalog

    def evaluate(
        self,
        role_id: str,
        answers: list[dict[str, Any]],
        structured_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role = self.catalog.get_role(role_id)
        answers_by_question = {item["question_id"]: item for item in answers}
        self._validate_answers(role, answers_by_question)

        target_level = self._extract_target_level(role, answers_by_question)
        raw_scores = self._extract_scores(role, answers_by_question)
        scores, score_adjustments = self._merge_extracted_scores(
            role=role,
            raw_scores=raw_scores,
            structured_profile=structured_profile,
        )
        total_score = sum(scores.values())
        max_score = len(scores) * 3

        coverage_map = {
            level["id"]: self._coverage_for_level(role, level["id"], scores)
            for level in role["levels"]
        }
        current_level = self._determine_current_level(
            role=role,
            scores=scores,
            total_score=total_score,
            coverage_map=coverage_map,
        )
        next_level = self._next_level(role, current_level)
        strengths = self._collect_strengths(role, scores, current_level)
        gaps_to_next_level = self._build_gaps(role, scores, next_level) if next_level else []
        gaps_to_target_level = self._build_gaps(role, scores, target_level)
        roadmap = self._build_roadmap(
            role=role,
            scores=scores,
            current_level=current_level,
            target_level=target_level,
            target_gaps=gaps_to_target_level,
            next_gaps=gaps_to_next_level,
        )
        project_ideas = self._project_ideas(role, current_level, target_level, next_level)
        reasoning = self._build_reasoning(
            role=role,
            total_score=total_score,
            max_score=max_score,
            coverage_map=coverage_map,
            current_level=current_level,
            target_level=target_level,
            strengths=strengths,
            target_gaps=gaps_to_target_level,
            next_gaps=gaps_to_next_level,
            structured_profile=structured_profile,
            score_adjustments=score_adjustments,
        )
        summary = self._build_summary(
            role=role,
            current_level=current_level,
            target_level=target_level,
            next_level=next_level,
            target_gaps=gaps_to_target_level,
            strengths=strengths,
        )

        level_map = self.catalog.level_map(role)
        coverage_by_level = [
            {
                "level": level["id"],
                "label": level["label"],
                "percent": coverage_map[level["id"]],
            }
            for level in role["levels"]
        ]

        return {
            "assessment_id": 0,
            "role_id": role["role"]["id"],
            "role_title": role["role"]["title"],
            "current_level": current_level,
            "current_level_label": level_map[current_level]["label"],
            "target_level": target_level,
            "target_level_label": level_map[target_level]["label"],
            "next_level": next_level,
            "next_level_label": level_map[next_level]["label"] if next_level else None,
            "total_score": total_score,
            "max_score": max_score,
            "coverage_by_level": coverage_by_level,
            "strengths": strengths,
            "gaps_to_next_level": gaps_to_next_level,
            "gaps_to_target_level": gaps_to_target_level,
            "roadmap": roadmap,
            "project_ideas": project_ideas,
            "reasoning": reasoning,
            "summary": summary,
            "structured_profile": structured_profile,
            "score_adjustments": score_adjustments,
            "breakdown": self._build_breakdown(role, scores),
        }

    def _validate_answers(
        self, role: dict[str, Any], answers_by_question: dict[str, dict[str, Any]]
    ) -> None:
        missing_questions = [
            question["id"]
            for question in role["questions"]
            if question["id"] not in answers_by_question
        ]
        if missing_questions:
            raise AssessmentError(
                f"Missing answers for questions: {', '.join(missing_questions)}"
            )

        invalid_questions = []
        for question in role["questions"]:
            answer = answers_by_question[question["id"]]
            if question["kind"] == "free_text":
                if not (answer.get("text") or "").strip():
                    invalid_questions.append(question["id"])
            else:
                if not (answer.get("option_id") or "").strip():
                    invalid_questions.append(question["id"])

        if invalid_questions:
            raise AssessmentError(
                f"Invalid answers for questions: {', '.join(invalid_questions)}"
            )

    def _extract_target_level(
        self, role: dict[str, Any], answers_by_question: dict[str, dict[str, Any]]
    ) -> str:
        target_question = next(
            question for question in role["questions"] if question["kind"] == "meta"
        )
        selected_option_id = answers_by_question[target_question["id"]]["option_id"]
        option_map = {option["id"]: option for option in target_question["options"]}
        try:
            return option_map[selected_option_id]["value"]
        except KeyError as error:
            raise AssessmentError("Invalid target level option") from error

    def _extract_scores(
        self, role: dict[str, Any], answers_by_question: dict[str, dict[str, Any]]
    ) -> dict[str, int]:
        scores: dict[str, int] = {}

        for question in role["questions"]:
            if question["kind"] != "competency":
                continue

            option_map = {option["id"]: option for option in question["options"]}
            selected_option_id = answers_by_question[question["id"]]["option_id"]
            try:
                selected_option = option_map[selected_option_id]
            except KeyError as error:
                raise AssessmentError(
                    f"Invalid option {selected_option_id} for {question['id']}"
                ) from error
            scores[question["competency_id"]] = int(selected_option["score"])

        return scores

    def _merge_extracted_scores(
        self,
        *,
        role: dict[str, Any],
        raw_scores: dict[str, int],
        structured_profile: dict[str, Any] | None,
    ) -> tuple[dict[str, int], list[str]]:
        if not structured_profile:
            return raw_scores, []

        suggested_scores = structured_profile.get("suggested_scores")
        if not isinstance(suggested_scores, dict):
            return raw_scores, []

        competency_map = self.catalog.competency_map(role)
        final_scores = dict(raw_scores)
        adjustments: list[str] = []

        for competency_id, extracted_value in suggested_scores.items():
            if competency_id not in competency_map:
                continue

            try:
                extracted_score = max(0, min(3, int(extracted_value)))
            except (TypeError, ValueError):
                continue

            current_score = final_scores.get(competency_id, 0)
            boosted_score = max(current_score, min(current_score + 1, extracted_score))
            if boosted_score <= current_score:
                continue

            final_scores[competency_id] = boosted_score
            adjustments.append(
                f"{competency_map[competency_id]['title']}: {current_score} → {boosted_score}"
            )

        return final_scores, adjustments

    def _coverage_for_level(
        self, role: dict[str, Any], level_id: str, scores: dict[str, int]
    ) -> int:
        requirements = role["level_requirements"][level_id]["required_competencies"]
        competency_map = self.catalog.competency_map(role)

        total_weight = 0.0
        achieved_weight = 0.0

        for competency_id, required_score in requirements.items():
            metadata = competency_map[competency_id]
            weight = float(metadata.get("weight", 1.0))
            actual_score = scores.get(competency_id, 0)
            total_weight += weight
            achieved_weight += min(actual_score / required_score, 1.0) * weight

        if total_weight == 0:
            return 0

        return round((achieved_weight / total_weight) * 100)

    def _determine_current_level(
        self,
        role: dict[str, Any],
        scores: dict[str, int],
        total_score: int,
        coverage_map: dict[str, int],
    ) -> str:
        current_level = role["levels"][0]["id"]

        for level in role["levels"]:
            level_id = level["id"]
            rules = role["level_requirements"][level_id]
            required_competencies = rules["required_competencies"]
            mandatory_count = len(required_competencies)
            reached_mandatory = sum(
                1
                for competency_id, required_score in required_competencies.items()
                if scores.get(competency_id, 0) >= required_score
            )
            mandatory_ratio = reached_mandatory / mandatory_count if mandatory_count else 0

            if (
                total_score >= int(rules["min_total_score"])
                and coverage_map[level_id] >= int(rules["min_coverage_percent"])
                and mandatory_ratio >= float(rules.get("min_mandatory_ratio", 0.0))
            ):
                current_level = level_id

        return current_level

    def _next_level(self, role: dict[str, Any], level_id: str) -> str | None:
        level_ids = [level["id"] for level in role["levels"]]
        position = level_ids.index(level_id)
        if position == len(level_ids) - 1:
            return None
        return level_ids[position + 1]

    def _collect_strengths(
        self, role: dict[str, Any], scores: dict[str, int], current_level: str
    ) -> list[str]:
        competency_map = self.catalog.competency_map(role)
        current_requirements = role["level_requirements"][current_level]["required_competencies"]

        ranked = sorted(
            scores.items(),
            key=lambda item: (
                item[1],
                competency_map[item[0]].get("weight", 1.0),
                competency_map[item[0]]["title"],
            ),
            reverse=True,
        )

        strengths = []
        for competency_id, score in ranked:
            requirement = current_requirements.get(competency_id, 1)
            if score >= max(requirement, 1):
                strengths.append(competency_map[competency_id]["title"])
            if len(strengths) == 4:
                break

        if strengths:
            return strengths

        return [competency_map[competency_id]["title"] for competency_id, _ in ranked[:3]]

    def _build_gaps(
        self, role: dict[str, Any], scores: dict[str, int], target_level: str | None
    ) -> list[dict[str, Any]]:
        if not target_level:
            return []

        competency_map = self.catalog.competency_map(role)
        requirements = role["level_requirements"][target_level]["required_competencies"]

        gaps = []
        for competency_id, target_score in requirements.items():
            current_score = scores.get(competency_id, 0)
            if current_score >= target_score:
                continue

            metadata = competency_map[competency_id]
            priority = (target_score - current_score) * float(metadata.get("weight", 1.0))
            gaps.append(
                {
                    "competency_id": competency_id,
                    "title": metadata["title"],
                    "current_score": current_score,
                    "target_score": target_score,
                    "recommended_action": metadata["roadmap_action"],
                    "why_it_matters": metadata["why_it_matters"],
                    "_priority": priority,
                }
            )

        gaps.sort(key=lambda item: (item["_priority"], item["title"]), reverse=True)
        for item in gaps:
            item.pop("_priority", None)

        return gaps

    def _build_roadmap(
        self,
        role: dict[str, Any],
        scores: dict[str, int],
        current_level: str,
        target_level: str,
        target_gaps: list[dict[str, Any]],
        next_gaps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        roadmap_source = target_gaps or next_gaps
        if not roadmap_source and current_level != target_level:
            roadmap_source = self._build_gaps(role, scores, current_level)

        if roadmap_source:
            return [
                {
                    "step": index,
                    "focus": gap["title"],
                    "action": gap["recommended_action"],
                }
                for index, gap in enumerate(roadmap_source[:4], start=1)
            ]

        if current_level == "senior":
            return [
                {
                    "step": 1,
                    "focus": "Архитектура и влияние",
                    "action": "Зафиксируй инженерные стандарты, проводи ревью решений и усиливай влияние на команду.",
                },
                {
                    "step": 2,
                    "focus": "Менторинг",
                    "action": "Поддерживай рост команды через код-ревью, knowledge sharing и технические инициативы.",
                },
            ]

        next_level = self._next_level(role, current_level)
        if next_level:
            next_level_gaps = self._build_gaps(role, scores, next_level)
            return [
                {
                    "step": index,
                    "focus": gap["title"],
                    "action": gap["recommended_action"],
                }
                for index, gap in enumerate(next_level_gaps[:4], start=1)
            ]

        return []

    def _project_ideas(
        self,
        role: dict[str, Any],
        current_level: str,
        target_level: str,
        next_level: str | None,
    ) -> list[str]:
        if self._level_rank(role, target_level) > self._level_rank(role, current_level):
            bucket = target_level
        elif next_level:
            bucket = next_level
        else:
            bucket = current_level

        return role.get("project_ideas", {}).get(bucket, [])[:2]

    def _build_reasoning(
        self,
        role: dict[str, Any],
        total_score: int,
        max_score: int,
        coverage_map: dict[str, int],
        current_level: str,
        target_level: str,
        strengths: list[str],
        target_gaps: list[dict[str, Any]],
        next_gaps: list[dict[str, Any]],
        structured_profile: dict[str, Any] | None,
        score_adjustments: list[str],
    ) -> list[str]:
        level_map = self.catalog.level_map(role)
        current_label = level_map[current_level]["label"]
        target_label = level_map[target_level]["label"]

        reasoning = [
            f"Суммарный балл: {total_score} из {max_score}. Покрытие уровня {current_label}: {coverage_map[current_level]}%.",
        ]

        extracted_skills = []
        if structured_profile:
            raw_skills = structured_profile.get("normalized_skills", [])
            if isinstance(raw_skills, list):
                extracted_skills = [str(item) for item in raw_skills[:5]]
        if extracted_skills:
            reasoning.append(
                f"Из свободного текста распознаны навыки: {', '.join(extracted_skills)}."
            )

        reasoning.append(f"Лучше всего у тебя выглядят: {', '.join(strengths[:3])}.")

        if score_adjustments:
            reasoning.append(
                f"NLP extraction усилил оценку по текстовым сигналам: {', '.join(score_adjustments[:2])}."
            )

        dominant_gaps = target_gaps or next_gaps
        if dominant_gaps:
            gap_titles = ", ".join(item["title"] for item in dominant_gaps[:3])
            if target_gaps and self._level_rank(role, current_level) >= self._level_rank(
                role, target_level
            ):
                reasoning.append(
                    f"Чтобы увереннее держать уровень {target_label}, усили: {gap_titles}."
                )
            else:
                reasoning.append(
                    f"Ближайшие ограничения для роста до {target_label}: {gap_titles}."
                )
        else:
            reasoning.append(
                f"Ключевые требования для цели {target_label} уже в основном закрыты."
            )

        return reasoning

    def _build_summary(
        self,
        role: dict[str, Any],
        current_level: str,
        target_level: str,
        next_level: str | None,
        target_gaps: list[dict[str, Any]],
        strengths: list[str],
    ) -> str:
        level_map = self.catalog.level_map(role)
        current_label = level_map[current_level]["label"]
        target_label = level_map[target_level]["label"]

        if target_gaps:
            gap_titles = ", ".join(item["title"] for item in target_gaps[:3])
            if self._level_rank(role, current_level) >= self._level_rank(role, target_level):
                return (
                    f"Ты уже находишься примерно на уровне {current_label}, "
                    f"но чтобы держать его увереннее, стоит усилить: {gap_titles}."
                )
            return (
                f"Сейчас твой профиль ближе всего к уровню {current_label}. "
                f"До {target_label} в первую очередь стоит усилить: {gap_titles}."
            )

        if self._level_rank(role, current_level) >= self._level_rank(role, target_level):
            if next_level:
                next_label = level_map[next_level]["label"]
                return (
                    f"Ты уже закрываешь базовые требования цели {target_label}. "
                    f"Следующий шаг для роста до {next_label}: {', '.join(strengths[:2])} закрепить на реальных задачах и расширить глубину."
                )
            return (
                f"Профиль уверенно соответствует уровню {current_label}. "
                "Дальше стоит усиливать архитектурное влияние и инженерное лидерство."
            )

        return (
            f"Сильнее всего у тебя развиты: {', '.join(strengths[:3])}. "
            f"Этого пока недостаточно, чтобы уверенно выйти на {target_label}."
        )

    def _build_breakdown(
        self, role: dict[str, Any], scores: dict[str, int]
    ) -> list[dict[str, Any]]:
        return [
            {
                "competency_id": competency["id"],
                "title": competency["title"],
                "score": scores.get(competency["id"], 0),
                "max_score": 3,
            }
            for competency in role["competencies"]
        ]

    @staticmethod
    def _level_rank(role: dict[str, Any], level_id: str) -> int:
        level_ids = [level["id"] for level in role["levels"]]
        return level_ids.index(level_id)
