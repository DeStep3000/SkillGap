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

    return "\n".join(lines)


def format_result(result: dict) -> str:
    lines = [
        f"<b>{escape(result['role_title'])}</b>",
        "",
        f"<b>Текущий уровень:</b> {escape(result['current_level_label'])}",
        f"<b>Цель:</b> {escape(result['target_level_label'])}",
        f"<b>Баллы:</b> {result['total_score']}/{result['max_score']}",
    ]

    created_at = result.get("created_at")
    if created_at:
        lines.append(f"<b>Дата анализа:</b> {escape(created_at.replace('T', ' ')[:19])}")

    lines.extend(["", "<b>Покрытие матрицы:</b>"])
    for item in result["coverage_by_level"]:
        lines.append(f"• {escape(item['label'])} — {item['percent']}%")

    lines.extend(["", "<b>Почему такой результат:</b>"])
    for reason in result["reasoning"]:
        lines.append(f"• {escape(reason)}")

    if result.get("narrative_explanation"):
        lines.extend(["", "<b>Объяснение от LLM:</b>"])
        lines.append(escape(result["narrative_explanation"]))
        if result.get("llm_used") and result.get("llm_model"):
            lines.append(
                f"<i>Источник: {escape(result['llm_provider'])} / {escape(result['llm_model'])}</i>"
            )

    structured_profile = result.get("structured_profile") or {}
    if structured_profile:
        normalized_skills = structured_profile.get("normalized_skills") or []
        if normalized_skills:
            lines.extend(["", "<b>NLP extraction распознал:</b>"])
            lines.append(
                "• " + escape(", ".join(str(item) for item in normalized_skills[:8]))
            )
        extraction_summary = structured_profile.get("summary")
        if extraction_summary:
            lines.append(escape(str(extraction_summary)))

    if result.get("score_adjustments"):
        lines.extend(["", "<b>Что дало free-text в оценке:</b>"])
        for item in result["score_adjustments"][:4]:
            lines.append(f"• {escape(item)}")

    if result["strengths"]:
        lines.extend(["", "<b>Сильные стороны:</b>"])
        for item in result["strengths"]:
            lines.append(f"• {escape(item)}")

    gaps = result["gaps_to_target_level"] or result["gaps_to_next_level"]
    if gaps:
        if result["gaps_to_target_level"] and result["current_level"] == result["target_level"]:
            label = "Что укрепить внутри текущего уровня"
        elif result["gaps_to_target_level"]:
            label = "Что подтянуть до цели"
        else:
            label = "Что подтянуть до следующего уровня"
        lines.extend(["", f"<b>{label}:</b>"])
        for gap in gaps[:5]:
            lines.append(
                f"• {escape(gap['title'])} ({gap['current_score']} → {gap['target_score']})"
            )

    if result["roadmap"]:
        lines.extend(["", "<b>Roadmap:</b>"])
        for item in result["roadmap"]:
            lines.append(
                f"{item['step']}. <b>{escape(item['focus'])}</b> — {escape(item['action'])}"
            )

    if result["project_ideas"]:
        lines.extend(["", "<b>Мини-проекты:</b>"])
        for idea in result["project_ideas"]:
            lines.append(f"• {escape(idea)}")

    lines.extend(["", f"<b>Итог:</b> {escape(result['summary'])}"])
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
        lines.extend(["", "<b>Почему такой match:</b>"])
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
