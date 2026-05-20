# Telegram AI Chat Bot - Production-Ready

A production-grade Telegram AI chat bot with Telegram Stars payments, async database, and modern error handling.

## Features

✨ **AI Capabilities**
- Multiple AI model selection (GPT-4o, GPT-4.1, Claude 3.5 Sonnet, Free OSS)
- Async OpenRouter API integration with retry logic
- Long response handling (automatic message chunking)

💳 **Payments**
- Telegram Stars payment integration
- Atomic balance updates (prevent race conditions)
- Payment history tracking
- Multiple package options

👤 **User Management**
- Per-user question balance system
- User statistics and profile management
- Model preference persistence
- Comprehensive logging

🔒 **Security**
- Environment variable configuration
- Input validation on all user messages
- Secure payment payload validation
- No hardcoded credentials

⚡ **Performance**
- Async/await throughout (no blocking operations)
- Reusable HTTP client for API calls
- Atomic database transactions
- Efficient message chunking

## Project Structure

```
.claude/
├── main.py              # Bot implementation with handlers
├── config.py            # Configuration and constants
├── database.py          # Async SQLite operations
├── services.py          # AI and payment services
├── errors.py            # Custom exceptions
├── requirements.txt     # Python dependencies
└── users.db            # SQLite database (auto-created)

.env                     # Environment variables (create from .env.example)
.env.example            # Environment template
```

## Installation

### 1. Clone and Setup

```bash
cd your-project-directory
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENROUTER_API_KEY=your_api_key_here
```

### 3. Run

```bash
python -m .claude.main
```

## Configuration

All settings are in `config.py`:

- **AI Models**: Modify `AVAILABLE_MODELS` dict
- **Payment Packages**: Adjust `STARS_PER_PACKAGE` and `QUESTIONS_PER_PACKAGE`
- **Message Limits**: `MESSAGE_CHAR_LIMIT` and `CAPTION_CHAR_LIMIT`
- **API Retries**: `MAX_RETRIES` and `RETRY_DELAY`

## Architecture

### Modules

**config.py**
- Centralized configuration management
- Environment variable validation
- Constants and defaults
- Helper methods for model/payment validation

**database.py**
- Async SQLite with `aiosqlite`
- Context managers for safe DB access
- Atomic transactions for balance updates
- Payment history tracking
- User statistics

**services.py**
- `AIService`: OpenRouter API integration
  - Reusable HTTP client
  - Retry logic with exponential backoff
  - Rate limit handling
  - Error logging
- `PaymentService`: Payment validation
  - Payload validation
  - Stars calculation
  - Duplicate prevention

**errors.py**
- Custom exception hierarchy
- Error classification utilities
- HTTP status code helpers

**main.py**
- `BotManager`: Central bot coordination
- Handler methods for all interactions
- FSM (Finite State Machine) for user flow
- Message chunking for long responses
- Comprehensive error handling

## Key Improvements

### 1. Security ✅
- ❌ **Before**: Hardcoded API keys in code
- ✅ **After**: Environment variables with validation

- ❌ **Before**: No input validation
- ✅ **After**: Validates all user inputs (text length, message type, callback data)

- ❌ **Before**: No payment validation
- ✅ **After**: Secure payment payload validation before processing

### 2. Database ✅
- ❌ **Before**: Synchronous sqlite3 (blocking operations)
- ✅ **After**: Async aiosqlite (non-blocking, better performance)

- ❌ **Before**: Race conditions on balance updates
- ✅ **After**: Atomic transactions with BEGIN/COMMIT

- ❌ **Before**: Manual connection management
- ✅ **After**: Context managers for safe resource handling

### 3. Error Handling ✅
- ❌ **Before**: Generic exception handling
- ✅ **After**: Custom exceptions with proper classification

- ❌ **Before**: No retry logic for API calls
- ✅ **After**: Exponential backoff with MAX_RETRIES

- ❌ **Before**: Silent failures
- ✅ **After**: Comprehensive logging at all levels

### 4. Performance ✅
- ❌ **Before**: New HTTP client per request
- ✅ **After**: Single reusable AsyncClient

- ❌ **Before**: No handling for long responses
- ✅ **After**: Automatic message chunking respects Telegram limits

- ❌ **Before**: Inefficient database queries
- ✅ **After**: Optimized with proper transactions

### 5. Code Quality ✅
- ✅ Type hints on all functions
- ✅ Comprehensive docstrings
- ✅ Modular architecture (separation of concerns)
- ✅ PEP 8 compliant
- ✅ Logging at appropriate levels
- ✅ No code duplication
- ✅ Clear error messages for users

### 6. User Experience ✅
- Typing indicator while processing
- Clear error messages
- Better menu organization
- Model descriptions
- Payment success confirmation with stats
- Balance shown in responses

## Usage Examples

### Starting the Bot
```bash
python -m .claude.main
```

### User Flow
1. `/start` - Show main menu
2. User selects "Choose Model" → Pick desired AI model
3. User selects "Buy Questions" → Choose package → Complete payment
4. User selects "Ask Question" → Type question → Get AI response

### Database

The bot automatically creates `users.db` with:
- **users table**: user_id, username, questions_balance, selected_model, stats, timestamps
- **payments table**: payment_id, user_id, amount_stars, questions_added, status, timestamp

### Logging

Configure logging level in `.env`:
```env
LOG_LEVEL=DEBUG  # For development
LOG_LEVEL=INFO   # For production
```

Example log output:
```
2024-01-15 10:30:45 - __main__ - INFO - Bot manager initialized
2024-01-15 10:30:46 - services - INFO - OpenRouter API call successful
2024-01-15 10:30:47 - database - INFO - Payment recorded: user 123456, 10 stars, 100 questions
```

## Payment System

### Telegram Stars Configuration

Telegram Stars is Telegram's native currency:
- No provider token needed (leave `TELEGRAM_PAYMENT_PROVIDER_TOKEN` empty)
- Payments are instant
- Currency code: `XTR`

### Package Structure

Default packages (configurable in `config.py`):
- **Small**: 10 Stars → 100 Questions
- **Medium**: 50 Stars → 500 Questions
- **Large**: 100 Stars → 1000 Questions

### Payment Flow

1. User clicks "⭐ Buy Questions"
2. Bot validates and creates invoice
3. User completes payment in Telegram
4. Bot receives `successful_payment` update
5. Balance is atomically updated
6. Confirmation sent to user

## API Reference

### BotManager Methods

```python
async initialize()              # Initialize bot and services
async close()                  # Cleanup and close services
async send_typing_action()     # Show typing indicator
async handle_*()              # Event handlers
async _process_question()     # Question processing logic
```

### Database Methods

```python
async initialize()                           # Create tables
async get_or_create_user()                  # User management
async get_user_balance()                    # Get questions balance
async add_user_balance()                    # Add questions (atomic)
async deduct_user_balance()                 # Deduct questions (atomic)
async set_user_model()                      # Set selected model
async record_payment()                      # Log payment
async get_user_stats()                      # Get user statistics
```

### AIService Methods

```python
async initialize()                          # Setup HTTP client
async call_openrouter()                     # Call AI with retries
async get_available_models()                # List available models
```

## Error Handling

The bot handles:
- ❌ Network timeouts → Retry with backoff
- ❌ Rate limits (429) → Exponential retry
- ❌ Server errors (5xx) → Retry with backoff
- ❌ Invalid model → Validation error with message
- ❌ Insufficient balance → Clear user message
- ❌ Database errors → Transaction rollback
- ❌ Invalid messages → Input validation

## Monitoring

Monitor these log levels:
- `ERROR`: Critical issues (manual intervention needed)
- `WARNING`: Recoverable issues (retries, etc.)
- `INFO`: Normal operation events
- `DEBUG`: Detailed diagnostic information

## Production Deployment

### Recommended Setup

1. Use environment variables from secrets manager
2. Run with proper logging (file rotation)
3. Use a process manager (systemd, supervisor)
4. Monitor bot health and error rates
5. Regular database backups

### Performance Tips

- Adjust `MAX_RETRIES` and `RETRY_DELAY` based on your API quota
- Monitor database size (add cleanup for old payments)
- Consider database replication for redundancy
- Use load balancer for multiple bot instances

## Troubleshooting

### "TELEGRAM_BOT_TOKEN not set"
- Check `.env` file exists and has `TELEGRAM_BOT_TOKEN`
- Verify token format is correct
- Ensure no extra spaces in `.env`

### "OpenRouter API timeout"
- Check internet connection
- Verify `OPENROUTER_API_KEY` is valid
- Check OpenRouter service status
- Increase `OPENROUTER_TIMEOUT` in config

### Database locked error
- Ensure only one bot instance is running
- Check file permissions on `users.db`
- Verify available disk space

### Payment not processing
- Verify Telegram Bot API token has payments enabled
- Check bot is registered with `@BotFather`
- Ensure user hasn't hit payment limits

## License

MIT License - feel free to use and modify

## Support

For issues:
1. Check logs (set `LOG_LEVEL=DEBUG`)
2. Verify environment variables
3. Test API keys independently
4. Check database file exists and is readable
