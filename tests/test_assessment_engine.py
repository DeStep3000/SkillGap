from __future__ import annotations

import unittest
from pathlib import Path

from app.services.assessment import AssessmentEngine
from app.services.catalog import RoleCatalog


DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"


class AssessmentEngineNarrativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = RoleCatalog(DATA_DIR)
        cls.engine = AssessmentEngine(cls.catalog)
        cls.role = cls.catalog.get_role("python_web_developer")

    def test_summary_mentions_actual_level_when_target_is_already_below_current(self) -> None:
        summary = self.engine._build_summary(
            role=self.role,
            current_level="middle",
            target_level="junior",
            next_level="senior",
            target_gaps=[],
            strengths=["Python core", "FastAPI/Django и REST API"],
        )

        self.assertIn("Цель Junior уже закрыта", summary)
        self.assertIn("ближе к Middle", summary)
        self.assertIn("Senior", summary)

    def test_reasoning_uses_next_level_when_target_is_already_closed(self) -> None:
        reasoning = self.engine._build_reasoning(
            role=self.role,
            total_score=19,
            max_score=30,
            coverage_map={"junior": 100, "middle": 100, "senior": 71},
            current_level="middle",
            target_level="junior",
            next_level="senior",
            strengths=["Python core", "FastAPI/Django и REST API"],
            target_gaps=[],
            next_gaps=[
                {"title": "Тестирование"},
                {"title": "PostgreSQL и SQL"},
            ],
            structured_profile=None,
            score_adjustments=[],
        )

        self.assertTrue(
            any("Цель Junior уже закрыта" in item and "Senior" in item for item in reasoning)
        )
        self.assertFalse(any("роста до Junior" in item for item in reasoning))


if __name__ == "__main__":
    unittest.main()
