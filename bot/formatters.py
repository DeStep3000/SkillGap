from __future__ import annotations

from html import escape


def format_question(role_title: str, question: dict, index: int, total: int) -> str:
    lines = [
        f"<b>{escape(role_title)}</b>",
        f"Вопрос {index} из {total}",
        "",
        f"<b>{escape(question['title'])}</b>",
    ]

    help_text = question.get("help_text")
    if help_text:
        lines.extend(["", escape(help_text)])

    if question.get("kind") == "free_text":
        lines.extend(["", "<i>Ответь следующим сообщением в свободной форме.</i>"])
    else:
        lines.extend(["", "<b>Варианты ответа:</b>"])
        for option_index, option in enumerate(question.get("options", []), start=1):
            lines.append(f"{option_index}. {escape(option['label'])}")
            description = option.get("description")
            if description:
                lines.append(f"<i>{escape(description)}</i>")
        lines.extend(["", "<i>Выбери номер кнопкой ниже.</i>"])

    return "\n".join(lines)


from html import escape


def format_result(result: dict) -> str:
    lines = []

    role_title = escape(result["role_title"])
    current_level = escape(result["current_level_label"])
    target_level = escape(result["target_level_label"])

    lines.append(f"<b>{role_title}</b>")
    lines.append("")
    lines.append(f"<b>Твой текущий уровень:</b> {current_level}")

    if result.get("current_level") != result.get("target_level"):
        lines.append(f"<b>Цель:</b> {target_level}")

    created_at = result.get("created_at")
    if created_at:
        lines.append(f"<b>Дата анализа:</b> {escape(created_at.replace('T', ' ')[:19])}")

    if result.get("summary"):
        lines.extend(["", f"<b>Коротко:</b> {escape(result['summary'])}"])

    if result.get("strengths"):
        lines.extend(["", "<b>Сильные стороны:</b>"])
        for item in result["strengths"][:4]:
            lines.append(f"• {escape(item)}")

    gaps = result.get("gaps_to_target_level") or result.get("gaps_to_next_level") or []
    if gaps:
        if result.get("gaps_to_target_level") and result.get("current_level") == result.get("target_level"):
            label = "Что стоит укрепить"
        elif result.get("gaps_to_target_level"):
            label = "Что мешает перейти к цели"
        else:
            label = "Что мешает перейти на следующий уровень"

        lines.extend(["", f"<b>{label}:</b>"])
        for gap in gaps[:5]:
            lines.append(f"• {escape(gap['title'])}")

    if result.get("roadmap"):
        lines.extend(["", "<b>Что делать дальше:</b>"])
        for item in result["roadmap"][:4]:
            lines.append(
                f"{item['step']}. <b>{escape(item['focus'])}</b> — {escape(item['action'])}"
            )

    if result.get("project_ideas"):
        lines.extend(["", "<b>Практика:</b>"])
        for idea in result["project_ideas"][:2]:
            lines.append(f"• {escape(idea)}")

    if result.get("narrative_explanation"):
        lines.extend(["", "<b>Краткий разбор:</b>"])
        lines.append(escape(result["narrative_explanation"]))

    lines.extend(["", "<b>Детали оценки:</b>"])
    lines.append(f"• Баллы: {result['total_score']}/{result['max_score']}")

    coverage = result.get("coverage_by_level") or []
    if coverage:
        coverage_parts = [f"{escape(item['label'])} — {item['percent']}%" for item in coverage]
        lines.append("• Покрытие матрицы: " + "; ".join(coverage_parts))

    if result.get("reasoning"):
        lines.extend(["", "<b>Почему я так оценил твой уровень:</b>"])
        for reason in result["reasoning"][:5]:
            lines.append(f"• {escape(reason)}")

    structured_profile = result.get("structured_profile") or {}
    normalized_skills = structured_profile.get("normalized_skills") or []
    extraction_summary = structured_profile.get("summary")

    if normalized_skills or extraction_summary:
        lines.extend(["", "<b>Что я понял из твоих ответов:</b>"])
        if normalized_skills:
            lines.append("• " + escape(", ".join(str(item) for item in normalized_skills[:8])))
        if extraction_summary:
            lines.append(escape(str(extraction_summary)))

    if result.get("score_adjustments"):
        lines.extend(["", "<b>Что дополнительно повлияло на результат:</b>"])
        for item in result["score_adjustments"][:4]:
            lines.append(f"• {escape(item)}")

    return "\n".join(lines)

def format_history(items: list[dict]) -> str:
    lines = ["<b>История оценок</b>", ""]
    for item in items:
        created_at = item["created_at"].replace("T", " ")[:19]
        lines.append(
            f"• {escape(created_at)} — {escape(item['current_level_label'])} "
            f"({item['total_score']}/{item['max_score']})"
        )
    lines.append("")
    lines.append("Выбери нужный анализ кнопкой ниже.")
    return "\n".join(lines)


def format_vacancy_result(result: dict) -> str:
    lines = [
        "<b>Сравнение с вакансией</b>",
        "",
        f"<b>Роль:</b> {escape(result['role_title'])}",
        f"<b>Текущий уровень:</b> {escape(result['current_level_label'])}",
        f"<b>Match:</b> {result['match_percent']}%",
    ]

    vacancy_source_url = result.get("vacancy_source_url")
    vacancy_source_title = result.get("vacancy_source_title")
    if vacancy_source_url:
        link_label = escape(vacancy_source_title or "Открыть вакансию")
        lines.append(f'<b>Источник:</b> <a href="{escape(vacancy_source_url)}">{link_label}</a>')
    elif vacancy_source_title:
        lines.append(f"<b>Источник:</b> {escape(vacancy_source_title)}")

    created_at = result.get("created_at")
    if created_at:
        lines.append(f"<b>Дата анализа:</b> {escape(created_at.replace('T', ' ')[:19])}")

    if result.get("vacancy_summary"):
        lines.extend(["", "<b>Что выделено из вакансии:</b>", escape(result["vacancy_summary"])])

    if result.get("matched_skills"):
        lines.extend(["", "<b>Уже совпадает:</b>"])
        for item in result["matched_skills"][:6]:
            lines.append(f"• {escape(item)}")

    if result.get("partial_matches"):
        lines.extend(["", "<b>Частично совпадает:</b>"])
        for item in result["partial_matches"][:6]:
            lines.append(f"• {escape(item)}")

    if result.get("missing_skills"):
        lines.extend(["", "<b>Не хватает:</b>"])
        for item in result["missing_skills"][:6]:
            lines.append(f"• {escape(item)}")

    if result.get("priority_gaps"):
        lines.extend(["", "<b>Приоритетно подтянуть:</b>"])
        for item in result["priority_gaps"][:5]:
            lines.append(f"• {escape(item)}")

    if result.get("reasoning"):
        lines.extend(["", "<b>Почему такой результат:</b>"])
        for item in result["reasoning"]:
            lines.append(f"• {escape(item)}")

    if result.get("llm_used") and result.get("llm_model"):
        lines.extend(
            [
                "",
                f"<i>Extraction: {escape(result['llm_provider'])} / {escape(result['llm_model'])}</i>",
            ]
        )

    return "\n".join(lines)
