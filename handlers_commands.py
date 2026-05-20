"""
Command handlers router.
Handles /start, /cancel, and other commands.
"""

import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database import Database
from keyboards import Keyboards

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def handle_start(message: types.Message, db: Database) -> None:
    """
    Handle /start command.
    Shows main menu with user stats.
    """
    try:
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"

        # Get/create user
        user = await db.get_or_create_user(user_id, username)
        balance = user["questions_balance"]
        model = user["selected_model"]

        text = (
            f"🤖 *Welcome to AI Chat Bot!*\n\n"
            f"Your Profile:\n"
            f"📊 Questions: `{balance}`\n"
            f"🧠 Model: `{model}`\n\n"
            f"Choose an action:"
        )

        await message.answer(
            text,
            reply_markup=Keyboards.main_menu(),
            parse_mode="Markdown",
        )
        logger.info(f"Start handler: user={user_id}")

    except Exception as e:
        logger.exception(f"Error in start handler: {e}")
        await message.answer("❌ Failed to load your profile. Please try again.")


@router.message(Command("cancel"))
async def handle_cancel(message: types.Message, state: FSMContext) -> None:
    """
    Handle /cancel command.
    Clears FSM state and returns to main menu.
    """
    try:
        await state.clear()
        text = (
            "❌ Cancelled.\n\n"
            "Send /start to return to main menu."
        )
        await message.answer(text)
        logger.info(f"Cancel command: user={message.from_user.id}")

    except Exception as e:
        logger.exception(f"Error in cancel handler: {e}")
