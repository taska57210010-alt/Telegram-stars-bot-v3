"""
Telegram AI Chat Bot - Production-Ready Implementation

Features:
- AI model selection with OpenRouter
- Telegram Stars payment integration
- Async database with SQLite
- Comprehensive error handling
- Type hints and logging
- Modular architecture
"""

import asyncio
import logging
import sys
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import config
from database import Database
from errors import (
    APIError,
    DatabaseError,
    InsufficientBalanceError,
    InvalidModelError,
)
from services import AIService, OpenRouterError, PaymentService

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=config.LOG_LEVEL,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


# FSM States
class UserState(StatesGroup):
    """User conversation states."""

    waiting_for_question = State()
    confirming_payment = State()


class BotManager:
    """Main bot manager class."""

    def __init__(self) -> None:
        """Initialize bot manager."""
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.db = Database(config.DATABASE_PATH)
        self.ai_service = AIService()

    async def initialize(self) -> None:
        """Initialize bot and services."""
        self.bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        self.dp = Dispatcher()
        await self.db.initialize()
        await self.ai_service.initialize()
        logger.info("Bot manager initialized")

    async def close(self) -> None:
        """Close bot and services."""
        if self.bot:
            await self.bot.session.close()
        await self.ai_service.close()
        logger.info("Bot manager closed")

    async def send_typing_action(self, chat_id: int) -> None:
        """Send typing action to indicate bot is processing."""
        if self.bot:
            try:
                await self.bot.send_chat_action(chat_id, "typing")
            except Exception as e:
                logger.warning(f"Failed to send chat action: {e}")

    @staticmethod
    def split_message(text: str, limit: int = config.MESSAGE_CHAR_LIMIT) -> list:
        """
        Split long message into chunks respecting Telegram limits.

        Args:
            text: Text to split
            limit: Character limit per message

        Returns:
            List of message chunks
        """
        if len(text) <= limit:
            return [text]

        chunks = []
        current_chunk = ""

        for paragraph in text.split("\n"):
            if len(current_chunk) + len(paragraph) + 1 > limit:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk += (
                    paragraph if not current_chunk else f"\n{paragraph}"
                )

        if current_chunk:
            chunks.append(current_chunk)

        return chunks if chunks else [text[:limit]]

    async def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Get main menu keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🧠 Choose Model", callback_data="choose_model")],
                [
                    InlineKeyboardButton(
                        text="⭐ Buy Questions",
                        callback_data="buy_questions",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💬 Ask Question",
                        callback_data="ask_question",
                    )
                ],
            ]
        )

    async def get_models_keyboard(self) -> InlineKeyboardMarkup:
        """Get model selection keyboard."""
        models = config.AVAILABLE_MODELS
        buttons = [
            [InlineKeyboardButton(text=f"🤖 {name.upper()}", callback_data=f"model_{key}")]
            for key, name in models.items()
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    async def get_payment_packages_keyboard(self) -> InlineKeyboardMarkup:
        """Get payment packages keyboard."""
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"⭐ 10 Stars (100 questions)",
                        callback_data="pay_small",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"⭐ 50 Stars (500 questions)",
                        callback_data="pay_medium",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"⭐ 100 Stars (1000 questions)",
                        callback_data="pay_large",
                    )
                ],
                [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
            ]
        )

    async def handle_start(self, message: Message) -> None:
        """
        Handle /start command.

        Args:
            message: Telegram message
        """
        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"

        try:
            user = await self.db.get_or_create_user(user_id, username)
            balance = user["questions_balance"]
            model = user["selected_model"]

            text = f"""🤖 *Welcome to AI Chat Bot!*

Your Profile:
📊 Questions: `{balance}`
🧠 Model: `{model}`

Choose an action:"""

            await message.answer(
                text,
                reply_markup=await self.get_main_menu_keyboard(),
                parse_mode="Markdown",
            )
        except DatabaseError as e:
            logger.error(f"Database error in start handler: {e}")
            await message.answer("❌ Failed to load your profile. Please try again.")

    async def handle_choose_model(self, callback_query: CallbackQuery) -> None:
        """
        Handle model selection button.

        Args:
            callback_query: Telegram callback query
        """
        try:
            text = "🧠 *Select an AI Model:*\n\n"
            models_info = {
                "gpt4o": "Latest GPT-4 Optimized",
                "gpt41": "GPT-4.1 Turbo",
                "claude_sonnet": "Claude 3.5 Sonnet",
                "free": "Free OSS (Limited)",
            }
            for key, desc in models_info.items():
                text += f"• `{key}` - {desc}\n"

            await callback_query.message.edit_text(
                text,
                reply_markup=await self.get_models_keyboard(),
                parse_mode="Markdown",
            )
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in choose_model handler: {e}")
            await callback_query.answer("❌ Failed to load models", show_alert=True)

    async def handle_model_selected(self, callback_query: CallbackQuery) -> None:
        """
        Handle model selection confirmation.

        Args:
            callback_query: Telegram callback query
        """
        user_id = callback_query.from_user.id
        model_key = callback_query.data.replace("model_", "")

        try:
            # Validate model
            config.get_model_by_key(model_key)

            await self.db.set_user_model(user_id, model_key)
            await callback_query.message.edit_text(
                f"✅ *Model updated to:* `{model_key}`\n\n"
                "Use /start to continue.",
                parse_mode="Markdown",
            )
            await callback_query.answer("Model updated!")
        except InvalidModelError:
            logger.warning(f"Invalid model selection attempt: {model_key}")
            await callback_query.answer(
                "❌ Invalid model selected", show_alert=True
            )
        except DatabaseError as e:
            logger.error(f"Database error updating model: {e}")
            await callback_query.answer(
                "❌ Failed to update model", show_alert=True
            )

    async def handle_buy_questions(self, callback_query: CallbackQuery) -> None:
        """
        Handle buy questions button.

        Args:
            callback_query: Telegram callback query
        """
        try:
            text = "⭐ *Choose a package:*"
            await callback_query.message.edit_text(
                text,
                reply_markup=await self.get_payment_packages_keyboard(),
                parse_mode="Markdown",
            )
            await callback_query.answer()
        except Exception as e:
            logger.error(f"Error in buy_questions handler: {e}")
            await callback_query.answer("❌ Failed to load packages", show_alert=True)

    async def handle_payment_initiation(self, callback_query: CallbackQuery) -> None:
        """
        Handle payment package selection and initiate invoice.

        Args:
            callback_query: Telegram callback query
        """
        user_id = callback_query.from_user.id
        package = callback_query.data.replace("pay_", "")

        try:
            stars = config.get_stars_for_package(package)
            questions = config.get_questions_for_package(package)

            if not stars or not questions:
                await callback_query.answer("❌ Invalid package", show_alert=True)
                return

            payload = f"stars_{stars}"

            prices = [LabeledPrice(label=f"{stars} Telegram Stars", amount=stars)]

            await self.bot.send_invoice(
                chat_id=user_id,
                title="AI Questions Package",
                description=f"Get {questions} AI questions for {stars} Telegram Stars",
                payload=payload,
                provider_token="",  # Empty for Telegram Stars
                currency="XTR",  # Telegram Stars currency
                prices=prices,
                is_flexible=False,
            )
            await callback_query.answer()
            logger.info(f"Payment invoice sent to user {user_id}")

        except Exception as e:
            logger.error(f"Payment initiation error: {e}")
            await callback_query.answer(
                "❌ Failed to initiate payment", show_alert=True
            )

    async def handle_pre_checkout(self, pre_checkout_query: PreCheckoutQuery) -> None:
        """
        Handle pre-checkout validation.

        Args:
            pre_checkout_query: Telegram pre-checkout query
        """
        try:
            # Validate payment payload
            payload = pre_checkout_query.invoice_payload
            if not PaymentService.validate_payment_payload(payload):
                logger.warning(f"Invalid payment payload: {payload}")
                await self.bot.answer_pre_checkout_query(
                    pre_checkout_query.id,
                    ok=False,
                    error_message="Invalid payment data",
                )
                return

            await self.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=True,
            )
            logger.info(f"Pre-checkout validated for user {pre_checkout_query.from_user.id}")

        except Exception as e:
            logger.error(f"Pre-checkout error: {e}")
            await self.bot.answer_pre_checkout_query(
                pre_checkout_query.id,
                ok=False,
                error_message="Validation failed",
            )

    async def handle_successful_payment(self, message: Message) -> None:
        """
        Handle successful payment.

        Args:
            message: Telegram message with successful payment
        """
        user_id = message.from_user.id
        payment = message.successful_payment

        try:
            payload = payment.invoice_payload
            stars = PaymentService.extract_stars_amount(payload)

            if not stars:
                logger.error(f"Invalid payment payload for user {user_id}: {payload}")
                await message.answer("❌ Payment processed but failed to add questions. Contact support.")
                return

            questions = PaymentService.get_questions_for_stars(stars)

            # Record payment and update balance
            payment_id = await self.db.record_payment(
                user_id, stars, questions, "completed"
            )
            new_balance = await self.db.add_user_balance(user_id, questions)

            await message.answer(
                f"✅ *Payment Successful!*\n\n"
                f"💰 {stars} Telegram Stars received\n"
                f"➕ {questions} questions added\n"
                f"📊 New balance: `{new_balance}` questions\n\n"
                "Use /start to ask questions!",
                parse_mode="Markdown",
            )

            logger.info(
                f"Payment completed: user={user_id}, "
                f"stars={stars}, questions={questions}, payment_id={payment_id}"
            )

        except DatabaseError as e:
            logger.error(f"Database error processing payment for {user_id}: {e}")
            await message.answer(
                "✅ Payment received but failed to update balance. Please contact support."
            )

    async def handle_ask_question(
        self, callback_query: CallbackQuery, state: FSMContext
    ) -> None:
        """
        Handle ask question button.

        Args:
            callback_query: Telegram callback query
            state: FSM context
        """
        user_id = callback_query.from_user.id

        try:
            balance = await self.db.get_user_balance(user_id)

            if balance <= 0:
                await callback_query.message.edit_text(
                    "❌ *No Questions Remaining*\n\n"
                    "Please buy more questions using the button below.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="⭐ Buy Questions",
                                    callback_data="buy_questions",
                                )
                            ]
                        ]
                    ),
                )
                await callback_query.answer()
                return

            await state.set_state(UserState.waiting_for_question)
            await callback_query.message.edit_text(
                f"💬 *Ask Your Question*\n\n"
                f"Questions remaining: `{balance}`",
                parse_mode="Markdown",
            )
            await callback_query.answer()

        except DatabaseError as e:
            logger.error(f"Database error in ask_question: {e}")
            await callback_query.answer("❌ Failed to load balance", show_alert=True)

    async def handle_message(
        self, message: Message, state: FSMContext
    ) -> None:
        """
        Handle regular messages (question responses).

        Args:
            message: Telegram message
            state: FSM context
        """
        # Validate message type
        if not message.text:
            await message.answer("❌ Please send a text message")
            return

        user_id = message.from_user.id
        username = message.from_user.username or f"user_{user_id}"
        user_text = message.text.strip()

        # Validate input
        if not user_text or len(user_text) > 4000:
            await message.answer(
                "❌ Please send a message between 1 and 4000 characters"
            )
            return

        current_state = await state.get_state()

        if current_state == UserState.waiting_for_question:
            await self._process_question(message, user_id, user_text, state)
        else:
            # Not in question state, offer main menu
            try:
                user = await self.db.get_or_create_user(user_id, username)
                balance = user["questions_balance"]
                model = user["selected_model"]

                await message.answer(
                    f"📊 Your stats:\n"
                    f"Questions: `{balance}`\n"
                    f"Model: `{model}`\n\n"
                    "Use /start to access the menu",
                    parse_mode="Markdown",
                    reply_markup=await self.get_main_menu_keyboard(),
                )
            except DatabaseError as e:
                logger.error(f"Database error in message handler: {e}")
                await message.answer("❌ Failed to load your profile")

    async def _process_question(
        self,
        message: Message,
        user_id: int,
        question_text: str,
        state: FSMContext,
    ) -> None:
        """
        Process user question with AI.

        Args:
            message: Telegram message
            user_id: User ID
            question_text: Question text
            state: FSM context
        """
        try:
            # Check balance
            balance = await self.db.get_user_balance(user_id)
            if balance <= 0:
                await message.answer(
                    "❌ No questions remaining. Use /start to buy more."
                )
                await state.clear()
                return

            # Get user's selected model
            selected_model = await self.db.get_user_model(user_id)

            # Send typing indicator
            await self.send_typing_action(user_id)

            # Call AI service
            logger.info(
                f"Processing question from user {user_id} with model {selected_model}"
            )
            ai_response = await self.ai_service.call_openrouter(
                question_text, selected_model
            )

            # Deduct balance
            if not await self.db.deduct_user_balance(user_id, 1):
                await message.answer(
                    "❌ Insufficient balance. Please try again later."
                )
                await state.clear()
                return

            new_balance = await self.db.get_user_balance(user_id)

            # Split and send response
            chunks = self.split_message(ai_response)
            for chunk in chunks:
                await message.answer(chunk)

            # Send stats
            await message.answer(
                f"📊 Questions remaining: `{new_balance}`",
                parse_mode="Markdown",
            )

            logger.info(f"Question processed successfully for user {user_id}")
            await state.clear()

        except OpenRouterError as e:
            logger.error(f"OpenRouter error for user {user_id}: {e}")
            await message.answer(
                f"❌ AI service error: {str(e)}\n\n"
                "Your question was not counted. Please try again."
            )
            await state.clear()

        except DatabaseError as e:
            logger.error(f"Database error processing question: {e}")
            await message.answer(
                "❌ Database error. Please try again later."
            )
            await state.clear()

        except Exception as e:
            logger.error(f"Unexpected error processing question: {e}")
            await message.answer(
                "❌ An unexpected error occurred. Please try again."
            )
            await state.clear()

    async def handle_cancel(self, callback_query: CallbackQuery, state: FSMContext) -> None:
        """
        Handle cancel button.

        Args:
            callback_query: Telegram callback query
            state: FSM context
        """
        await state.clear()
        await callback_query.message.edit_text("❌ Cancelled")
        await callback_query.answer()

    def register_handlers(self) -> None:
        """Register all message and callback handlers."""
        # Commands
        self.dp.message.register(self.handle_start, Command("start"))

        # Callback queries
        self.dp.callback_query.register(
            self.handle_choose_model, F.data == "choose_model"
        )
        self.dp.callback_query.register(
            self.handle_model_selected, F.data.startswith("model_")
        )
        self.dp.callback_query.register(
            self.handle_buy_questions, F.data == "buy_questions"
        )
        self.dp.callback_query.register(
            self.handle_payment_initiation, F.data.startswith("pay_")
        )
        self.dp.callback_query.register(
            self.handle_ask_question, F.data == "ask_question"
        )
        self.dp.callback_query.register(
            self.handle_cancel, F.data == "cancel"
        )

        # Payment handlers
        self.dp.pre_checkout_query.register(self.handle_pre_checkout)
        self.dp.message.register(
            self.handle_successful_payment, F.successful_payment
        )

        # Message handler (must be last)
        self.dp.message.register(self.handle_message)

        logger.info("All handlers registered")

    async def run(self) -> None:
        """Run the bot."""
        try:
            logger.info("Starting bot polling...")
            await self.dp.start_polling(self.bot)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            raise


async def main() -> None:
    """Main entry point."""
    manager = BotManager()
    try:
        await manager.initialize()
        manager.register_handlers()
        await manager.run()
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(main())
