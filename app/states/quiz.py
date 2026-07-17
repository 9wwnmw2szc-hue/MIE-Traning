from aiogram.fsm.state import State, StatesGroup


class QuizStates(StatesGroup):
    answering = State()
    finished = State()
    conflict = State()
