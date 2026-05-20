# Quick Start Guide

## Installation

### 1. Install Python Dependencies
```bash
cd c:\Users\autos\Desktop\Free-Claude
pip install -r requirements.txt
```

### 2. Create `.env` File
```bash
# Copy template (if exists)
copy .env.example .env

# Edit .env with your credentials
TELEGRAM_BOT_TOKEN=<your-bot-token-from-botfather>
OPENROUTER_API_KEY=<your-openrouter-api-key>
```

### 3. Verify Configuration
```bash
python -c "from .claude.config import config; print('✅ Config loaded')"
```

## Running the Bot

### Start the Bot
```bash
cd c:\Users\autos\Desktop\Free-Claude
python .\.claude\main_v3.py
```

### Expected Output
```
2026-05-20 10:15:23 - __main__ - INFO - Initializing bot application...
2026-05-20 10:15:24 - __main__ - INFO - Database initialized with indexes
2026-05-20 10:15:24 - __main__ - INFO - AI Service initialized
2026-05-20 10:15:24 - __main__ - INFO - ✅ Bot application initialized
2026-05-20 10:15:24 - __main__ - INFO - ✅ All handlers registered
2026-05-20 10:15:24 - __main__ - INFO - 🚀 Starting bot polling...
```

## Testing

### Test in Telegram
1. Find your bot in Telegram
2. Send `/start` - Should show main menu
3. Click "Ask Question" button
4. Send a question - Bot responds with AI answer
5. Click "Buy Questions" to test payment flow

### Manual Database Test
```python
import asyncio
from .claude.database import Database

async def test():
    db = Database("users.db")
    await db.initialize()
    
    # Get or create user
    user = await db.get_or_create_user(123456, "testuser")
    print(f"User: {user}")
    
    # Add questions
    balance = await db.add_user_balance(123456, 100)
    print(f"New balance: {balance}")

asyncio.run(test())
```

## Configuration

### Key Config Values (in `config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `max_retries` | 3 | OpenRouter retry attempts |
| `ai_request_timeout` | 120s | Max time for AI response |
| `typing_refresh_interval` | 4s | How often to refresh typing action |
| `rate_limit_questions` | 10/min | Anti-spam limit |
| `rate_limit_callbacks` | 5/sec | Anti-spam limit |

### Modifying Limits
Edit `.claude/config.py`:
```python
class Config(BaseSettings):
    rate_limit_questions: int = 20  # Change to 20/min
    ai_request_timeout: int = 180   # Change to 180s
```

## Troubleshooting

### "Failed to load configuration"
- Check `.env` file exists in project root
- Verify `TELEGRAM_BOT_TOKEN` and `OPENROUTER_API_KEY` are set

### "can't parse entities" Error
- This is caught by error handler and fallback to plain text
- Check logs for which model returned bad Markdown

### Database Locked Error
- Wait a moment and retry
- If persistent, delete `users.db` and restart (will reinitialize)

### Bot Not Responding
- Check logs for errors
- Verify Telegram API token is correct
- Check OpenRouter API key and rate limits

## Deployment Tips

### 1. Run in Background (Windows)
```powershell
# Using PS background job
Start-Job -ScriptBlock { 
    cd "c:\Users\autos\Desktop\Free-Claude"
    python .\.claude\main_v3.py
}
```

### 2. Monitor Bot Health
```bash
# Check last 50 log entries
python -c "
import subprocess
result = subprocess.run(['powershell', '-Command', '''
    get-process | where {$$_.Name -like '*python*'} | select Id, Name, @{Name='CPU%';Expression={'{0:N2}' -f ($$_.TotalProcessorTime).TotalSeconds}}
'''], capture_output=True)
print(result.stdout.decode())
"
```

### 3. Automatic Restart on Crash
Create `run_bot.py`:
```python
import subprocess
import time

while True:
    process = subprocess.Popen(["python", ".\\.\claude\\main_v3.py"])
    process.wait()
    time.sleep(5)  # Wait 5 seconds before restart
    print("Bot restarted...")
```

## Next Steps

1. **Review production architecture**: See `PRODUCTION_ARCHITECTURE.md`
2. **Test payment flow**: Use Telegram test version for Telegram Stars
3. **Set up monitoring**: Capture logs to file for analysis
4. **Optimize rate limits**: Adjust based on user load
5. **Add more models**: Edit `config.py` AVAILABLE_MODELS

## Support

- **Logs**: All actions logged to stdout with timestamps
- **Database**: SQLite file at `users.db` (SQL browser compatible)
- **Errors**: Check logs for full exception tracebacks

---

**For detailed architecture info, see: `PRODUCTION_ARCHITECTURE.md`**
