from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand, CallbackQuery, Message, User

from bot.client import ApiClientError, AssessmentApiClient
from bot.config import get_settings
from bot.formatters import format_history, format_question, format_result, format_vacancy_result
from bot.keyboards import history_keyboard, question_keyboard, result_keyboard, roles_keyboard
from bot.states import AssessmentFlow


router = Router()


def get_api_client() -> AssessmentApiClient:
    settings = get_settings()
    return AssessmentApiClient(
        base_url=settings.api_base_url,
        timeout_seconds=settings.timeout_seconds,
    )


async def register_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Узнать свой уровень"),
            BotCommand(command="menu", description="Главное меню"),
            BotCommand(command="history", description="Мой прогресс"),
            BotCommand(command="vacancy", description="Подхожу ли я вакансии"),
        ]
    )


async def render_role_menu(message: Message, state: FSMContext, *, edit: bool = False) -> None:
    api = get_api_client()
    roles = await api.list_roles()
    await state.clear()
    await state.set_state(AssessmentFlow.choosing_role)
    await state.update_data(roles=roles)

    text = "Привет! Я помогу определить твой уровень и покажу, что нужно прокачать. Выбери роль:"
    if edit:
        await safe_edit(message, text, roles_keyboard(roles))
        return
    await message.answer(text, reply_markup=roles_keyboard(roles))


async def safe_edit(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        await message.answer(text, reply_markup=reply_markup)


async def present_current_question(
    message: Message,
    state: FSMContext,
    *,
    edit: bool,
) -> None:
    data = await state.get_data()
    questions = data["questionnaire"]
    current_index = data["current_index"]

    if current_index >= len(questions):
        return

    question = questions[current_index]
    text = format_question(
        role_title=data["role_title"],
        question=question,
        index=current_index + 1,
        total=len(questions),
    )
    reply_markup = question_keyboard(question) if question["kind"] != "free_text" else None

    if edit:
        await safe_edit(message, text, reply_markup)
        return
    await message.answer(text, reply_markup=reply_markup)


async def finalize_assessment(
    message: Message,
    user: User,
    state: FSMContext,
    *,
    edit_loading: bool,
) -> None:
    data = await state.get_data()
    answers_map: dict[str, dict[str, Any]] = data["answers"]
    question_order = [question["id"] for question in data["questionnaire"]]
    answers = [
        {"question_id": question_id, **answers_map[question_id]}
        for question_id in question_order
    ]

    payload = {
        "telegram_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role_id": data["role_id"],
        "answers": answers,
    }

    if edit_loading:
        await safe_edit(message, "Анализирую твой профиль и готовлю рекомендации по развитию...")
    else:
        await message.answer("Анализирую твой профиль и готовлю рекомендации по развитию...")

    api = get_api_client()
    result = await api.create_assessment(payload)
    await state.clear()

    if edit_loading:
        await safe_edit(message, format_result(result), result_keyboard(result["assessment_id"]))
        return
    await message.answer(
        format_result(result),
        reply_markup=result_keyboard(result["assessment_id"]),
    )


async def prompt_for_vacancy(
    message: Message,
    state: FSMContext,
    *,
    assessment_id: int | None,
    edit: bool,
) -> None:
    await state.set_state(AssessmentFlow.awaiting_vacancy_url)
    await state.update_data(vacancy_assessment_id=assessment_id)
    text = (
        "Отправь ссылку на вакансию следующим сообщением.\n\n"
        "Я загружу страницу, вытащу описание вакансии и потом сравню его с твоим профилем: "
        "покажу совпадения, пробелы и что стоит прокачать в первую очередь."
    )
    if edit:
        await safe_edit(message, text)
        return
    await message.answer(text)


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    try:
        await render_role_menu(message, state)
    except ApiClientError as error:
        await message.answer(f"Не удалось получить данные от API: {error}")


@router.message(Command("menu"))
async def menu_handler(message: Message, state: FSMContext) -> None:
    try:
        await render_role_menu(message, state)
    except ApiClientError as error:
        await message.answer(f"Не удалось получить данные от API: {error}")


@router.message(Command("history"))
async def history_handler(message: Message) -> None:
    api = get_api_client()
    try:
        items = await api.get_history(message.from_user.id)
    except ApiClientError as error:
        await message.answer(f"Не удалось загрузить историю: {error}")
        return

    if not items:
        await message.answer("История пока пустая. Для начала узнай свой уровень.")
        return

    await message.answer(format_history(items), reply_markup=history_keyboard(items))


@router.message(Command("vacancy"))
async def vacancy_handler(message: Message, state: FSMContext) -> None:
    api = get_api_client()
    try:
        latest = await api.get_history(message.from_user.id)
    except ApiClientError as error:
        await message.answer(f"Не удалось проверить историю: {error}")
        return

    if not latest:
        await message.answer("Сначала пройди оценку уровня - тогда я смогу точно сравнить тебя с вакансией и показать пробелы.")
        return

    await prompt_for_vacancy(
        message,
        state,
        assessment_id=latest[0]["assessment_id"],
        edit=False,
    )


@router.callback_query(F.data.startswith("role:"))
async def role_selected(callback: CallbackQuery, state: FSMContext) -> None:
    role_id = callback.data.split(":", maxsplit=1)[1]
    api = get_api_client()

    try:
        questionnaire = await api.get_questionnaire(role_id)
    except ApiClientError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await state.set_state(AssessmentFlow.answering)
    await state.update_data(
        role_id=role_id,
        role_title=questionnaire["role"]["title"],
        questionnaire=questionnaire["questions"],
        current_index=0,
        answers={},
    )
    await callback.answer()
    await present_current_question(callback.message, state, edit=True)


@router.callback_query(F.data.startswith("answer:"))
async def answer_selected(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if not data or "questionnaire" not in data:
        await callback.answer("Сессия устарела, начни заново через /start", show_alert=True)
        return

    _, question_id, option_id = callback.data.split(":", maxsplit=2)
    questions = data["questionnaire"]
    current_index = data["current_index"]
    current_question = questions[current_index]

    if current_question["id"] != question_id:
        await callback.answer("Этот вопрос уже закрыт. Используй актуальные кнопки.", show_alert=True)
        return

    answers = data["answers"]
    answers[question_id] = {"option_id": option_id}
    await state.update_data(answers=answers, current_index=current_index + 1)
    await callback.answer()

    if current_index + 1 >= len(questions):
        try:
            await finalize_assessment(
                callback.message,
                callback.from_user,
                state,
                edit_loading=True,
            )
        except ApiClientError as error:
            await safe_edit(callback.message, f"Не удалось выполнить оценку: {error}")
        return

    await present_current_question(callback.message, state, edit=True)


@router.callback_query(F.data == "menu:restart")
async def restart_handler(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await render_role_menu(callback.message, state, edit=True)
        await callback.answer()
    except ApiClientError as error:
        await callback.answer(str(error), show_alert=True)


@router.callback_query(F.data == "menu:history")
async def history_menu_handler(callback: CallbackQuery) -> None:
    api = get_api_client()
    try:
        items = await api.get_history(callback.from_user.id)
    except ApiClientError as error:
        await callback.answer(str(error), show_alert=True)
        return

    if not items:
        await callback.answer("История пока пустая", show_alert=True)
        return

    await callback.answer()
    await safe_edit(callback.message, format_history(items), history_keyboard(items))


@router.callback_query(F.data.startswith("history:"))
async def history_item_handler(callback: CallbackQuery) -> None:
    assessment_id = int(callback.data.split(":", maxsplit=1)[1])
    api = get_api_client()

    try:
        result = await api.get_history_item(callback.from_user.id, assessment_id)
    except ApiClientError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.answer()
    await safe_edit(
        callback.message,
        format_result(result),
        result_keyboard(result["assessment_id"]),
    )


@router.callback_query(F.data.startswith("menu:vacancy:"))
async def vacancy_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    assessment_id = int(callback.data.split(":", maxsplit=2)[2])
    await callback.answer()
    await prompt_for_vacancy(
        callback.message,
        state,
        assessment_id=assessment_id,
        edit=True,
    )


@router.message(AssessmentFlow.answering)
async def free_text_answer_handler(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if not data or "questionnaire" not in data:
        await message.answer("Сессия устарела, начни заново через /start.")
        return

    questions = data["questionnaire"]
    current_index = data["current_index"]
    current_question = questions[current_index]

    if current_question["kind"] != "free_text":
        await message.answer("Для этого вопроса используй кнопки под сообщением.")
        return

    text_value = (message.text or "").strip()
    if not text_value:
        await message.answer("Нужен именно текстовый ответ. Напиши 2-4 предложения по вопросу.")
        return

    answers = data["answers"]
    answers[current_question["id"]] = {"text": text_value}
    await state.update_data(answers=answers, current_index=current_index + 1)

    if current_index + 1 >= len(questions):
        try:
            await finalize_assessment(
                message,
                message.from_user,
                state,
                edit_loading=False,
            )
        except ApiClientError as error:
            await message.answer(f"Не удалось выполнить оценку: {error}")
        return

    await present_current_question(message, state, edit=False)


@router.message(AssessmentFlow.awaiting_vacancy_url)
async def vacancy_url_handler(message: Message, state: FSMContext) -> None:
    vacancy_url = (message.text or "").strip()
    parsed_url = urlparse(vacancy_url)
    if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_url.netloc:
        await message.answer(
            "Нужна полная ссылка на вакансию, начиная с http:// или https://."
        )
        return

    data = await state.get_data()
    assessment_id = data.get("vacancy_assessment_id")
    payload = {
        "assessment_id": assessment_id,
        "vacancy_url": vacancy_url,
    }

    await message.answer(
        "Загружаю вакансию по ссылке, извлекаю описание и считаю совпадение с твоим профилем..."
    )
    api = get_api_client()
    try:
        result = await api.create_vacancy_analysis(message.from_user.id, payload)
    except ApiClientError as error:
        await message.answer(f"Не удалось проанализировать вакансию: {error}")
        return

    await state.clear()
    await message.answer(format_vacancy_result(result))


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await register_bot_commands(bot)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
