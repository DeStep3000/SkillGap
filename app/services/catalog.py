from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CatalogError(KeyError):
    pass


class RoleCatalog:
    def __init__(self, data_dir: Path) -> None:
        self._roles: dict[str, dict[str, Any]] = {}

        for path in sorted(data_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            role_id = payload["role"]["id"]
            self._roles[role_id] = payload

        if not self._roles:
            raise ValueError(f"No role definitions found in {data_dir}")

    def list_roles(self) -> list[dict[str, Any]]:
        return [
            {
                "id": role["role"]["id"],
                "title": role["role"]["title"],
                "description": role["role"].get("description"),
            }
            for role in self._roles.values()
        ]

    def get_role(self, role_id: str) -> dict[str, Any]:
        try:
            return self._roles[role_id]
        except KeyError as error:
            raise CatalogError(f"Unknown role: {role_id}") from error

    def get_questionnaire(self, role_id: str) -> dict[str, Any]:
        role = self.get_role(role_id)
        questions = []
        for question in role["questions"]:
            questions.append(
                {
                    "id": question["id"],
                    "kind": question["kind"],
                    "title": question["title"],
                    "help_text": question.get("help_text"),
                    "options": [
                        {
                            "id": option["id"],
                            "label": option["label"],
                            "description": option.get("description"),
                        }
                        for option in question.get("options", [])
                    ],
                }
            )

        return {
            "role": {
                "id": role["role"]["id"],
                "title": role["role"]["title"],
                "description": role["role"].get("description"),
            },
            "levels": [
                {"id": level["id"], "label": level["label"]}
                for level in role["levels"]
            ],
            "questions": questions,
        }

    @staticmethod
    def competency_map(role: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in role["competencies"]}

    @staticmethod
    def level_map(role: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in role["levels"]}
