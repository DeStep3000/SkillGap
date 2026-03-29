from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def roles_keyboard(roles: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role in roles:
        builder.button(text=role["title"], callback_data=f"role:{role['id']}")
    builder.adjust(1)
    return builder.as_markup()


def question_keyboard(question: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for option in question["options"]:
        builder.button(
            text=option["label"],
            callback_data=f"answer:{question['id']}:{option['id']}",
        )
    builder.adjust(1)
    return builder.as_markup()


def result_keyboard(assessment_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Сравнить вакансию",
        callback_data=f"menu:vacancy:{assessment_id}",
    )
    builder.button(text="История", callback_data="menu:history")
    builder.button(text="Пройти заново", callback_data="menu:restart")
    builder.adjust(1, 2)
    return builder.as_markup()


def history_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(
            text=f"{_short_date(item['created_at'])} • {item['current_level_label']}",
            callback_data=f"history:{item['assessment_id']}",
        )
    builder.button(text="Пройти заново", callback_data="menu:restart")
    builder.adjust(1)
    return builder.as_markup()


def _short_date(value: str) -> str:
    return value.replace("T", " ")[:16]
