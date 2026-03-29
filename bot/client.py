from __future__ import annotations

from typing import Any

import httpx


class ApiClientError(RuntimeError):
    pass


class AssessmentApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    async def list_roles(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/reference/roles")

    async def get_questionnaire(self, role_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/reference/roles/{role_id}/questionnaire")

    async def create_assessment(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/assessments", json=payload)

    async def get_history(self, telegram_id: int) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/v1/users/{telegram_id}/history")

    async def get_history_item(self, telegram_id: int, assessment_id: int) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/api/v1/users/{telegram_id}/history/{assessment_id}",
        )

    async def create_vacancy_analysis(
        self,
        telegram_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/users/{telegram_id}/vacancy-analyses",
            json=payload,
        )

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.request(method, path, json=json)

        if response.is_error:
            detail = self._extract_error(response)
            raise ApiClientError(detail)

        return response.json()

    @staticmethod
    def _extract_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"API error: {response.status_code}"

        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        return f"API error: {response.status_code}"
