from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class AssessmentRepository:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.engine: Engine = create_engine(
            database_url,
            future=True,
            pool_pre_ping=True,
        )

    def initialize(self) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGSERIAL PRIMARY KEY,
                        telegram_id BIGINT NOT NULL UNIQUE,
                        username TEXT,
                        full_name TEXT,
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS assessments (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        role_id TEXT NOT NULL,
                        current_level TEXT NOT NULL,
                        target_level TEXT NOT NULL,
                        total_score INTEGER NOT NULL,
                        max_score INTEGER NOT NULL,
                        summary_text TEXT NOT NULL,
                        answers_json TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_assessments_user_created_at
                    ON assessments (user_id, created_at DESC)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS vacancy_analyses (
                        id BIGSERIAL PRIMARY KEY,
                        assessment_id BIGINT NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
                        vacancy_text TEXT NOT NULL,
                        extracted_requirements_json TEXT NOT NULL,
                        match_percent INTEGER NOT NULL,
                        result_json TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_vacancy_analyses_assessment_created_at
                    ON vacancy_analyses (assessment_id, created_at DESC)
                    """
                )
            )

    def save_assessment(
        self,
        *,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
        role_id: str,
        answers: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> int:
        created_at = self._now()

        with self.engine.begin() as connection:
            user_id = int(
                connection.execute(
                    text(
                        """
                        INSERT INTO users (
                            telegram_id,
                            username,
                            full_name,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :telegram_id,
                            :username,
                            :full_name,
                            :created_at,
                            :updated_at
                        )
                        ON CONFLICT (telegram_id)
                        DO UPDATE SET
                            username = EXCLUDED.username,
                            full_name = EXCLUDED.full_name,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id
                        """
                    ),
                    {
                        "telegram_id": telegram_id,
                        "username": username,
                        "full_name": full_name,
                        "created_at": created_at,
                        "updated_at": created_at,
                    },
                ).scalar_one()
            )

            assessment_id = int(
                connection.execute(
                    text(
                        """
                        INSERT INTO assessments (
                            user_id,
                            role_id,
                            current_level,
                            target_level,
                            total_score,
                            max_score,
                            summary_text,
                            answers_json,
                            result_json,
                            created_at
                        )
                        VALUES (
                            :user_id,
                            :role_id,
                            :current_level,
                            :target_level,
                            :total_score,
                            :max_score,
                            :summary_text,
                            :answers_json,
                            :result_json,
                            :created_at
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "user_id": user_id,
                        "role_id": role_id,
                        "current_level": result["current_level"],
                        "target_level": result["target_level"],
                        "total_score": result["total_score"],
                        "max_score": result["max_score"],
                        "summary_text": result["summary"],
                        "answers_json": json.dumps(answers, ensure_ascii=False),
                        "result_json": json.dumps(result, ensure_ascii=False),
                        "created_at": created_at,
                    },
                ).scalar_one()
            )

        return assessment_id

    def list_assessments(self, telegram_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self.engine.begin() as connection:
            rows = (
                connection.execute(
                    text(
                        """
                        SELECT assessments.id,
                               assessments.role_id,
                               assessments.current_level,
                               assessments.target_level,
                               assessments.total_score,
                               assessments.max_score,
                               assessments.summary_text,
                               assessments.result_json,
                               assessments.created_at
                        FROM assessments
                        JOIN users ON users.id = assessments.user_id
                        WHERE users.telegram_id = :telegram_id
                        ORDER BY assessments.created_at DESC
                        LIMIT :limit
                        """
                    ),
                    {"telegram_id": telegram_id, "limit": limit},
                )
                .mappings()
                .all()
            )
        return [self._serialize_row(row) for row in rows]

    def get_assessment(self, telegram_id: int, assessment_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT assessments.id,
                               assessments.role_id,
                               assessments.current_level,
                               assessments.target_level,
                               assessments.total_score,
                               assessments.max_score,
                               assessments.summary_text,
                               assessments.answers_json,
                               assessments.result_json,
                               assessments.created_at
                        FROM assessments
                        JOIN users ON users.id = assessments.user_id
                        WHERE users.telegram_id = :telegram_id
                          AND assessments.id = :assessment_id
                        LIMIT 1
                        """
                    ),
                    {
                        "telegram_id": telegram_id,
                        "assessment_id": assessment_id,
                    },
                )
                .mappings()
                .first()
            )

        if not row:
            return None

        return self._serialize_row(row)

    def get_latest_assessment(self, telegram_id: int) -> dict[str, Any] | None:
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    text(
                        """
                        SELECT assessments.id,
                               assessments.role_id,
                               assessments.current_level,
                               assessments.target_level,
                               assessments.total_score,
                               assessments.max_score,
                               assessments.summary_text,
                               assessments.answers_json,
                               assessments.result_json,
                               assessments.created_at
                        FROM assessments
                        JOIN users ON users.id = assessments.user_id
                        WHERE users.telegram_id = :telegram_id
                        ORDER BY assessments.created_at DESC
                        LIMIT 1
                        """
                    ),
                    {"telegram_id": telegram_id},
                )
                .mappings()
                .first()
            )

        if not row:
            return None

        return self._serialize_row(row)

    def save_vacancy_analysis(
        self,
        *,
        assessment_id: int,
        vacancy_text: str,
        extracted_requirements: dict[str, Any],
        result: dict[str, Any],
    ) -> tuple[int, str]:
        created_at = self._now()
        with self.engine.begin() as connection:
            vacancy_analysis_id = int(
                connection.execute(
                    text(
                        """
                        INSERT INTO vacancy_analyses (
                            assessment_id,
                            vacancy_text,
                            extracted_requirements_json,
                            match_percent,
                            result_json,
                            created_at
                        )
                        VALUES (
                            :assessment_id,
                            :vacancy_text,
                            :extracted_requirements_json,
                            :match_percent,
                            :result_json,
                            :created_at
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "assessment_id": assessment_id,
                        "vacancy_text": vacancy_text,
                        "extracted_requirements_json": json.dumps(
                            extracted_requirements, ensure_ascii=False
                        ),
                        "match_percent": int(result["match_percent"]),
                        "result_json": json.dumps(result, ensure_ascii=False),
                        "created_at": created_at,
                    },
                ).scalar_one()
            )
        return vacancy_analysis_id, created_at.astimezone(UTC).replace(microsecond=0).isoformat()

    @staticmethod
    def _serialize_row(row: Any) -> dict[str, Any]:
        payload = dict(row)
        created_at = payload.get("created_at")
        if isinstance(created_at, datetime):
            payload["created_at"] = created_at.astimezone(UTC).replace(microsecond=0).isoformat()
        return payload

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(microsecond=0)
