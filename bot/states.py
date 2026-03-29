from aiogram.fsm.state import State, StatesGroup


class AssessmentFlow(StatesGroup):
    choosing_role = State()
    answering = State()
    awaiting_vacancy_text = State()
