from __future__ import annotations

import unittest

from app.services.llm_service import OpenRouterLLMService


class OpenRouterParserTests(unittest.TestCase):
    def test_assessment_enrichment_parser_accepts_trailing_commas(self) -> None:
        raw_content = """```json
{
  "narrative_explanation": "Короткое объяснение",
  "project_ideas": [
    "Идея 1",
    "Идея 2",
  ],
}
```"""

        parsed = OpenRouterLLMService._parse_assessment_enrichment_json(raw_content)

        self.assertEqual(parsed["narrative_explanation"], "Короткое объяснение")
        self.assertEqual(parsed["project_ideas"], ["Идея 1", "Идея 2"])

    def test_profile_parser_accepts_python_style_dict(self) -> None:
        raw_content = """{
  'normalized_skills': ['fastapi', 'pytest'],
  'strengths': ['backend'],
  'weaknesses': ['sql'],
  'task_types': ['crud'],
  'summary': 'Профиль backend-разработчика.',
  'suggested_scores': {
    'testing': 2,
    'unknown_competency': 3,
  },
}"""

        parsed = OpenRouterLLMService._parse_profile_json(
            raw_content,
            competency_map={"testing": "Тестирование"},
        )

        self.assertEqual(parsed["normalized_skills"], ["fastapi", "pytest"])
        self.assertEqual(parsed["summary"], "Профиль backend-разработчика.")
        self.assertEqual(parsed["suggested_scores"], {"testing": 2})


if __name__ == "__main__":
    unittest.main()
