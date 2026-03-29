from __future__ import annotations

from typing import Any

from app.services.catalog import RoleCatalog


class VacancyMatchingService:
    def __init__(self, catalog: RoleCatalog) -> None:
        self.catalog = catalog

    def match(
        self,
        *,
        role_id: str,
        assessment_result: dict[str, Any],
        vacancy_profile: dict[str, Any],
    ) -> dict[str, Any]:
        role = self.catalog.get_role(role_id)
        competency_map = self.catalog.competency_map(role)
        level_map = self.catalog.level_map(role)

        user_scores = {
            item["competency_id"]: int(item["score"])
            for item in assessment_result.get("breakdown", [])
        }
        user_skills = self._user_skills(role, assessment_result)
        requirements = self._normalize_requirements(vacancy_profile, competency_map)

        matched_skills: list[str] = []
        partial_matches: list[str] = []
        missing_skills: list[str] = []
        priority_candidates: list[tuple[int, int, str]] = []
        requirement_rows: list[dict[str, Any]] = []

        total_weight = 0.0
        achieved_weight = 0.0

        for requirement in requirements:
            importance_weight = {"high": 3.0, "medium": 2.0, "low": 1.0}[requirement["importance"]]
            total_weight += importance_weight

            normalized_skill = requirement["normalized_skill"]
            competency_id = requirement["competency_id"]
            target_score = requirement["target_score"]
            user_score = user_scores.get(competency_id, 0)
            has_skill = normalized_skill in user_skills

            if has_skill or user_score >= target_score:
                status = "matched"
                achieved_weight += importance_weight
                matched_skills.append(requirement["skill"])
            elif user_score > 0 or (target_score > 0 and user_score >= target_score - 1):
                status = "partial"
                achieved_weight += importance_weight * 0.5
                partial_matches.append(requirement["skill"])
                priority_candidates.append((int(importance_weight), target_score - user_score, requirement["skill"]))
            else:
                status = "missing"
                missing_skills.append(requirement["skill"])
                priority_candidates.append((int(importance_weight), target_score, requirement["skill"]))

            requirement_rows.append(
                {
                    "skill": requirement["skill"],
                    "normalized_skill": normalized_skill,
                    "competency_id": competency_id,
                    "competency_title": competency_map[competency_id]["title"],
                    "importance": requirement["importance"],
                    "target_score": target_score,
                    "match_status": status,
                    "user_score": user_score,
                }
            )

        match_percent = round((achieved_weight / total_weight) * 100) if total_weight else 0
        priority_candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        priority_gaps = []
        for _, _, skill in priority_candidates:
            if skill not in priority_gaps:
                priority_gaps.append(skill)
            if len(priority_gaps) == 5:
                break

        reasoning = [
            f"Match с вакансией: {match_percent}%.",
            self._coverage_line(matched_skills, partial_matches, missing_skills),
        ]
        vacancy_summary = vacancy_profile.get("summary")
        if vacancy_summary:
            reasoning.append(f"Из вакансии выделено: {vacancy_summary}")
        if priority_gaps:
            reasoning.append(f"Приоритетно подтянуть: {', '.join(priority_gaps[:3])}.")

        return {
            "vacancy_analysis_id": 0,
            "assessment_id": 0,
            "role_id": role_id,
            "role_title": role["role"]["title"],
            "current_level": assessment_result["current_level"],
            "current_level_label": level_map[assessment_result["current_level"]]["label"],
            "target_level": assessment_result["target_level"],
            "target_level_label": level_map[assessment_result["target_level"]]["label"],
            "match_percent": match_percent,
            "vacancy_summary": vacancy_summary,
            "reasoning": reasoning,
            "matched_skills": self._dedupe_preserve_order(matched_skills),
            "partial_matches": self._dedupe_preserve_order(partial_matches),
            "missing_skills": self._dedupe_preserve_order(missing_skills),
            "priority_gaps": priority_gaps,
            "requirements": requirement_rows,
            "llm_used": bool(vacancy_profile.get("llm_model")),
            "llm_provider": vacancy_profile.get("llm_provider"),
            "llm_model": vacancy_profile.get("llm_model"),
        }

    def _user_skills(self, role: dict[str, Any], assessment_result: dict[str, Any]) -> set[str]:
        skills = set()
        structured_profile = assessment_result.get("structured_profile") or {}
        normalized_skills = structured_profile.get("normalized_skills") or []
        if isinstance(normalized_skills, list):
            skills.update(str(item).strip().lower() for item in normalized_skills if str(item).strip())

        competency_map = self.catalog.competency_map(role)
        for item in assessment_result.get("breakdown", []):
            competency_id = item["competency_id"]
            score = int(item["score"])
            if score < 1:
                continue
            for signal in competency_map.get(competency_id, {}).get("signals", []):
                if signal:
                    skills.add(str(signal).strip().lower())

        return skills

    @staticmethod
    def _normalize_requirements(
        vacancy_profile: dict[str, Any],
        competency_map: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        raw_requirements = vacancy_profile.get("requirements", [])
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for item in raw_requirements:
            if not isinstance(item, dict):
                continue
            competency_id = str(item.get("competency_id", "")).strip()
            if competency_id not in competency_map:
                continue
            skill = str(item.get("skill", "")).strip() or competency_map[competency_id]["title"]
            normalized_skill = str(item.get("normalized_skill", "")).strip().lower() or skill.lower()
            importance = str(item.get("importance", "medium")).strip().lower()
            if importance not in {"high", "medium", "low"}:
                importance = "medium"
            try:
                target_score = max(1, min(3, int(item.get("target_score", 1))))
            except (TypeError, ValueError):
                target_score = 1

            key = (normalized_skill, competency_id)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "skill": skill,
                    "normalized_skill": normalized_skill,
                    "competency_id": competency_id,
                    "importance": importance,
                    "target_score": target_score,
                }
            )

        return normalized

    @staticmethod
    def _coverage_line(
        matched_skills: list[str],
        partial_matches: list[str],
        missing_skills: list[str],
    ) -> str:
        return (
            f"Совпадений: {len(set(matched_skills))}, "
            f"частичных совпадений: {len(set(partial_matches))}, "
            f"пробелов: {len(set(missing_skills))}."
        )

    @staticmethod
    def _dedupe_preserve_order(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
