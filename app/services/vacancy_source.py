from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover - depends on local environment
    BeautifulSoup = None


_IGNORED_TAGS = (
    "canvas",
    "footer",
    "form",
    "nav",
    "noscript",
    "script",
    "style",
    "svg",
    "template",
)
_META_DESCRIPTION_NAMES = {"description", "og:description", "twitter:description"}
_ROOT_ATTR_PATTERN = re.compile(
    r"(vacanc|job|position|role|description|details|content|posting|offer)",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")
_BOILERPLATE_MARKERS = (
    "cookie",
    "privacy policy",
    "terms of use",
    "sign in",
    "log in",
    "register",
    "subscribe",
    "подпис",
    "куки",
    "политик",
    "соглас",
    "войти",
    "зарегистр",
)
_JOB_HINTS = (
    "backend",
    "frontend",
    "fullstack",
    "developer",
    "engineer",
    "python",
    "java",
    "golang",
    "qa",
    "devops",
    "data",
    "product",
    "ios",
    "android",
    "vacancy",
    "job",
    "role",
    "skills",
    "stack",
    "requirements",
    "responsibilities",
    "qualifications",
    "must have",
    "nice to have",
    "experience",
    "salary",
    "remote",
    "гибрид",
    "удален",
    "ваканс",
    "требован",
    "обязанност",
    "услови",
    "опыт",
    "навык",
    "стек",
    "зп",
)
_JSON_LD_FIELDS = (
    "title",
    "name",
    "description",
    "skills",
    "qualifications",
    "responsibilities",
    "experienceRequirements",
    "employmentType",
    "industry",
)


class VacancySourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedVacancySource:
    source_url: str
    source_title: str | None
    vacancy_text: str


class VacancySourceService:
    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        max_text_length: int = 12000,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_text_length = max_text_length

    def extract_from_url(self, vacancy_url: str) -> ParsedVacancySource:
        normalized_url = self._normalize_url(vacancy_url)
        content_type, page_body, final_url = self._download_page(normalized_url)

        if "text/plain" in content_type:
            body_lines = self._prepare_lines(page_body)
            page_title = None
            description = None
            json_ld_lines: list[str] = []
        else:
            page_title, description, json_ld_lines, body_lines = self._extract_from_html(page_body)

        sections: list[str] = [f"Vacancy URL: {final_url}"]
        if page_title:
            sections.append(f"Vacancy title: {page_title}")
        if description:
            sections.append(f"Page summary: {description}")
        if json_ld_lines:
            sections.append("Structured vacancy details:\n" + "\n".join(json_ld_lines[:20]))
        if body_lines:
            sections.append("Vacancy page content:\n" + "\n".join(body_lines[:120]))

        vacancy_text = "\n\n".join(section for section in sections if section).strip()
        if not body_lines and not json_ld_lines:
            raise VacancySourceError("Could not extract readable vacancy content from the URL")

        return ParsedVacancySource(
            source_url=final_url,
            source_title=page_title,
            vacancy_text=vacancy_text[: self.max_text_length],
        )

    def _extract_from_html(
        self,
        page_body: str,
    ) -> tuple[str | None, str | None, list[str], list[str]]:
        if BeautifulSoup is None:
            raise VacancySourceError(
                "beautifulsoup4 is not installed. Run `uv sync` or install the dependency in the project virtualenv."
            )
        soup = BeautifulSoup(page_body, "html.parser")
        page_title = self._clean_inline_text(soup.title.get_text(" ", strip=True)) if soup.title else None
        description = self._extract_meta_description(soup)
        json_ld_lines = self._extract_json_ld_lines(self._extract_json_ld_blocks(soup))

        for node in soup.find_all(list(_IGNORED_TAGS)):
            node.decompose()

        body_lines = self._extract_body_lines(soup)
        return page_title or None, description or None, json_ld_lines, body_lines

    def _extract_meta_description(self, soup: BeautifulSoup) -> str | None:
        for meta_name in _META_DESCRIPTION_NAMES:
            tag = soup.find(
                "meta",
                attrs={
                    "name": lambda value: isinstance(value, str) and value.strip().lower() == meta_name
                },
            ) or soup.find(
                "meta",
                attrs={
                    "property": lambda value: isinstance(value, str)
                    and value.strip().lower() == meta_name
                },
            )
            if not tag:
                continue
            content = self._clean_inline_text(str(tag.get("content") or ""))
            if content:
                return content
        return None

    def _extract_json_ld_blocks(self, soup: BeautifulSoup) -> list[str]:
        result: list[str] = []
        for script in soup.find_all("script"):
            script_type = str(script.get("type") or "").strip().lower()
            if script_type != "application/ld+json":
                continue
            content = script.string if script.string is not None else script.get_text(" ", strip=True)
            if content and content.strip():
                result.append(content)
        return result

    def _extract_body_lines(self, soup: BeautifulSoup) -> list[str]:
        candidates = []
        seen: set[int] = set()

        for node in (
            soup.find("main"),
            soup.find("article"),
            soup.find(attrs={"role": "main"}),
            soup.body,
        ):
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append(node)

        for node in soup.find_all(["section", "div"], limit=40):
            attr_value = " ".join(
                part
                for part in (
                    str(node.get("id") or "").strip(),
                    " ".join(str(item) for item in (node.get("class") or [])),
                )
                if part
            )
            if not attr_value or not _ROOT_ATTR_PATTERN.search(attr_value):
                continue
            if id(node) in seen:
                continue
            seen.add(id(node))
            candidates.append(node)

        body_lines: list[str] = []
        for node in candidates:
            text = node.get_text("\n", strip=True)
            body_lines.extend(self._prepare_lines(text))
            if len(body_lines) >= 150:
                break

        if body_lines:
            return self._dedupe_lines(body_lines, limit=150)

        fallback_text = soup.get_text("\n", strip=True)
        return self._prepare_lines(fallback_text)

    def _download_page(self, vacancy_url: str) -> tuple[str, str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
        }

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = client.get(vacancy_url)
                response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise VacancySourceError(
                f"Could not load vacancy URL: HTTP {error.response.status_code}"
            ) from error
        except httpx.HTTPError as error:
            raise VacancySourceError(f"Could not load vacancy URL: {error}") from error

        content_type = (response.headers.get("content-type") or "").lower()
        if not any(
            allowed in content_type
            for allowed in ("text/html", "application/xhtml+xml", "text/plain")
        ):
            raise VacancySourceError(
                f"Vacancy URL returned unsupported content type: {content_type or 'unknown'}"
            )

        return content_type, response.text, str(response.url)

    @staticmethod
    def _normalize_url(vacancy_url: str) -> str:
        candidate = vacancy_url.strip()
        parsed = urlparse(candidate)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise VacancySourceError("Vacancy URL must start with http:// or https://")
        return candidate

    def _extract_json_ld_lines(self, json_ld_blocks: list[str]) -> list[str]:
        result: list[str] = []
        for block in json_ld_blocks:
            if not block.strip():
                continue
            try:
                payload = json.loads(block)
            except ValueError:
                continue
            self._collect_json_ld_strings(payload, result, inside_job_posting=False)
        return self._dedupe_lines(result, limit=30)

    def _collect_json_ld_strings(
        self,
        payload: Any,
        result: list[str],
        *,
        inside_job_posting: bool,
    ) -> None:
        if isinstance(payload, list):
            for item in payload:
                self._collect_json_ld_strings(
                    item,
                    result,
                    inside_job_posting=inside_job_posting,
                )
            return

        if not isinstance(payload, dict):
            return

        type_value = payload.get("@type")
        current_inside_job_posting = inside_job_posting or self._is_job_posting(type_value)
        if current_inside_job_posting:
            for field_name in _JSON_LD_FIELDS:
                if field_name not in payload:
                    continue
                for value in self._flatten_strings(payload[field_name]):
                    cleaned = self._clean_inline_text(value)
                    if cleaned:
                        result.append(cleaned)

        for value in payload.values():
            self._collect_json_ld_strings(
                value,
                result,
                inside_job_posting=current_inside_job_posting,
            )

    @staticmethod
    def _is_job_posting(type_value: Any) -> bool:
        if isinstance(type_value, list):
            return any(VacancySourceService._is_job_posting(item) for item in type_value)
        if not isinstance(type_value, str):
            return False
        return "jobposting" in type_value.replace(" ", "").lower()

    def _flatten_strings(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                result.extend(self._flatten_strings(item))
            return result
        if isinstance(value, dict):
            result: list[str] = []
            for key in ("text", "name", "title", "value"):
                if key in value:
                    result.extend(self._flatten_strings(value[key]))
            return result
        return []

    def _prepare_lines(self, raw_text: str) -> list[str]:
        lines = re.split(r"\n+", raw_text.replace("\r", "\n"))
        prepared: list[str] = []
        for line in lines:
            cleaned = self._clean_inline_text(line)
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if any(marker in lowered for marker in _BOILERPLATE_MARKERS):
                continue
            if (
                len(cleaned) < 20
                and "," not in cleaned
                and ":" not in cleaned
                and not any(marker in lowered for marker in _JOB_HINTS)
            ):
                continue
            prepared.append(cleaned)
        return self._dedupe_lines(prepared, limit=150)

    @staticmethod
    def _clean_inline_text(value: str) -> str:
        cleaned = value.replace("\xa0", " ").replace("\u200b", " ")
        cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip(" \t\n\r-•")
        return cleaned

    @staticmethod
    def _dedupe_lines(lines: list[str], *, limit: int) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for line in lines:
            lowered = line.lower()
            if not lowered or lowered in seen:
                continue
            seen.add(lowered)
            result.append(line)
            if len(result) >= limit:
                break
        return result
