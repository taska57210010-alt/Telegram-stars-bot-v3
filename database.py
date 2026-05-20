"""
Async database module using aiosqlite.
Handles all user data persistence.
"""

import aiosqlite
import logging
from contextlib import asynccontextmanager
from typing import Optional

from errors import DatabaseError

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str) -> None:
        """
        Initialize database manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    async def initialize(self) -> None:
        """Initialize database tables and indexes."""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable foreign keys
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Create users table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    questions_balance INTEGER DEFAULT 0,
                    selected_model TEXT DEFAULT 'free',
                    total_questions_used INTEGER DEFAULT 0,
                    total_stars_spent INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Create payments table with idempotency
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    telegram_charge_id TEXT UNIQUE,
                    amount_stars INTEGER NOT NULL,
                    questions_added INTEGER NOT NULL,
                    payment_status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
                """
            )
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(payment_status)",
                "CREATE INDEX IF NOT EXISTS idx_payments_telegram_id ON payments(telegram_charge_id)",
                "CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at)",
            ]
            
            for index_sql in indexes:
                try:
                    await db.execute(index_sql)
                except aiosqlite.IntegrityError:
                    pass  # Index already exists
            
            await db.commit()
            logger.info("Database initialized with indexes")

    @asynccontextmanager
    async def get_db(self):
        """Get database connection context manager."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def get_or_create_user(self, user_id: int, username: str) -> dict:
        """
        Get existing user or create new one.

        Args:
            user_id: Telegram user ID
            username: Telegram username

        Returns:
            User data dictionary
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with self.get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                user = await cursor.fetchone()

                if user:
                    return dict(user)

                # Create new user
                await db.execute(
                    """
                    INSERT INTO users
                    (user_id, username, questions_balance, selected_model)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, username, 0, "free"),
                )
                await db.commit()
                logger.info(f"New user created: {user_id} ({username})")

                cursor = await db.execute(
                    "SELECT * FROM users WHERE user_id = ?", (user_id,)
                )
                user = await cursor.fetchone()
                return dict(user)
        except Exception as e:
            logger.error(f"Database error in get_or_create_user: {e}")
            raise DatabaseError(f"Failed to get or create user: {e}") from e

    async def get_user_balance(self, user_id: int) -> int:
        """
        Get user's question balance.

        Args:
            user_id: Telegram user ID

        Returns:
            Questions balance
        """
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT questions_balance FROM users WHERE user_id = ?", (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_user_model(self, user_id: int) -> str:
        """
        Get user's selected model.

        Args:
            user_id: Telegram user ID

        Returns:
            Selected model key
        """
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT selected_model FROM users WHERE user_id = ?", (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else "free"

    async def set_user_model(self, user_id: int, model: str) -> None:
        """
        Update user's selected model.

        Args:
            user_id: Telegram user ID
            model: Model key to set
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            async with self.get_db() as db:
                await db.execute(
                    """
                    UPDATE users
                    SET selected_model = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (model, user_id),
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Database error in set_user_model: {e}")
            raise DatabaseError(f"Failed to set user model: {e}") from e

    async def add_user_balance(self, user_id: int, questions: int) -> int:
        """
        Add questions to user balance (atomic operation).

        Args:
            user_id: Telegram user ID
            questions: Number of questions to add

        Returns:
            New balance
            
        Raises:
            DatabaseError: If database operation fails
        """
        async with self.get_db() as db:
            await db.execute("BEGIN TRANSACTION")
            try:
                await db.execute(
                    """
                    UPDATE users
                    SET questions_balance = questions_balance + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                    """,
                    (questions, user_id),
                )
                await db.commit()

                cursor = await db.execute(
                    "SELECT questions_balance FROM users WHERE user_id = ?",
                    (user_id,),
                )
                result = await cursor.fetchone()
                new_balance = result[0] if result else 0
                logger.info(f"Added {questions} questions to user {user_id}")
                return new_balance
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to add balance: {e}")
                raise DatabaseError(f"Failed to add balance: {e}") from e

    async def deduct_user_balance(self, user_id: int, questions: int = 1) -> bool:
        """
        Deduct questions from user balance (atomic, race-condition safe).
        
        Uses atomic SQL to ensure balance check and deduction happen together.
        No pre-check needed - SQL handles it atomically.

        Args:
            user_id: Telegram user ID
            questions: Number of questions to deduct (default 1)

        Returns:
            True if deduction succeeded, False if insufficient balance

        Raises:
            DatabaseError: If database operation fails
        """
        async with self.get_db() as db:
            try:
                await db.execute("BEGIN TRANSACTION")
                
                # Atomic deduction: only succeeds if balance is sufficient
                # This prevents race conditions without pre-check
                cursor = await db.execute(
                    """
                    UPDATE users
                    SET questions_balance = questions_balance - ?,
                        total_questions_used = total_questions_used + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND questions_balance >= ?
                    """,
                    (questions, questions, user_id, questions),
                )
                
                # Check if update affected any rows
                affected = cursor.rowcount
                await db.commit()
                
                if affected > 0:
                    logger.info(f"Deducted {questions} questions from user {user_id}")
                    return True
                else:
                    logger.warning(f"Insufficient balance for user {user_id}")
                    return False
                    
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to deduct balance: {e}")
                raise DatabaseError(f"Failed to deduct balance: {e}") from e

    async def record_payment(
        self,
        user_id: int,
        amount_stars: int,
        questions_added: int,
        telegram_charge_id: Optional[str] = None,
        status: str = "pending",
    ) -> int:
        """
        Record a payment transaction (with idempotency).

        Args:
            user_id: Telegram user ID
            amount_stars: Stars amount
            questions_added: Questions added
            telegram_charge_id: Telegram charge ID (for idempotency)
            status: Payment status

        Returns:
            Payment ID

        Raises:
            ValueError: If payment already processed (duplicate)
            DatabaseError: If database operation fails
        """
        async with self.get_db() as db:
            try:
                # Check for duplicate payment (idempotency)
                if telegram_charge_id:
                    cursor = await db.execute(
                        "SELECT payment_id FROM payments WHERE telegram_charge_id = ?",
                        (telegram_charge_id,),
                    )
                    existing = await cursor.fetchone()
                    if existing:
                        logger.warning(
                            f"Payment already processed: {telegram_charge_id}"
                        )
                        raise ValueError(f"Payment already processed: {telegram_charge_id}")

                # Record new payment
                cursor = await db.execute(
                    """
                    INSERT INTO payments
                    (user_id, telegram_charge_id, amount_stars, questions_added, payment_status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, telegram_charge_id, amount_stars, questions_added, status),
                )
                await db.commit()
                
                logger.info(
                    f"Payment recorded: user={user_id}, stars={amount_stars}, "
                    f"questions={questions_added}, charge_id={telegram_charge_id}"
                )
                return cursor.lastrowid
                
            except ValueError:
                # Re-raise ValueError for duplicate payments
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to record payment: {e}")
                raise DatabaseError(f"Failed to record payment: {e}") from e

    async def mark_payment_completed(self, payment_id: int) -> None:
        """
        Mark payment as completed.

        Args:
            payment_id: Payment ID
        """
        async with self.get_db() as db:
            await db.execute(
                "UPDATE payments SET payment_status = 'completed' WHERE payment_id = ?",
                (payment_id,),
            )
            await db.commit()

    async def payment_exists(self, telegram_charge_id: str) -> bool:
        """
        Check if payment already processed (prevent duplicates).

        Args:
            telegram_charge_id: Telegram charge ID

        Returns:
            True if payment exists, False otherwise
        """
        async with self.get_db() as db:
            cursor = await db.execute(
                "SELECT 1 FROM payments WHERE telegram_charge_id = ? LIMIT 1",
                (telegram_charge_id,),
            )
            result = await cursor.fetchone()
            return result is not None
