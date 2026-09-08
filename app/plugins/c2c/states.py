"""FSM states for card-to-card manual payments."""

from aiogram.fsm.state import State, StatesGroup


class C2cStates(StatesGroup):
    waiting_for_receipt = State()
