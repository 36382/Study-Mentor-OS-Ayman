# ayman-os-agent

A smart local operating-system agent built in Python. It can list directories, read and write files, run shell commands, manage appointments, build parent reports, send alerts, and integrate with AWS Bedrock and Telegram.

## Features
- List files and directories
- Read and write files
- Run shell commands
- Manage appointments and calendar items
- Generate parent-facing daily reports
- Read and summarize the Study Mentor OS workbook
- Send email alerts
- Connect to AWS Bedrock for AI suggestions
- Start a Telegram bot listener
- Interactive REPL mode

## Quick start

```bash
python main.py --help
python main.py --interactive
python main.py "list current directory"
python main.py --read README.md
python main.py --run "python --version"
python main.py "add appointment review on 2026-09-17 at 09:00"
python main.py "report"
python main.py "show study sheet"
python main.py "today summary"
python main.py "check risk"
python main.py "ask bedrock how to organize my day"
```

## Secrets and environment

Do not place real secrets in the repository. Use a local `.env` file or OS environment variables. The project includes a sample template at `.env.example`.

```bash
copy .env.example .env
```

Then fill the values for:
- `SMTP_USER`, `SMTP_PASSWORD`, `PARENT_EMAIL`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (comma-separated IDs are supported)
- `AYMAN_STUDY_SHEET`, `STUDY_SHEET_PATH`, or `AYMAN_STUDY_SHEET_URL` for the study data
- `AI_BACKEND=auto`, `gemini`, or `bedrock`
- `GEMINI_API_KEY` or AWS Bedrock credentials

## Railway deployment

This repo is ready to deploy to Railway using either Docker or the Railway app config.

Files included:
- `Dockerfile`
- `railway.json`
- `Procfile`

To deploy:
1. Push this repository to GitHub.
2. Open Railway and create a new project from GitHub.
3. Select this repo.
4. Set the environment variables from `.env.example` in the Railway dashboard.
5. Deploy.

Example environment variables for Railway:

```bash
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=8778090214,7398495644
PARENT_EMAIL=parent@example.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_gmail@gmail.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_gmail@gmail.com
GEMINI_API_KEY=your_gemini_key
```

The default Google Sheet URL is the configured public Study Mentor sheet. Railway
downloads it as an XLSX workbook at startup; no Google credentials are required.

## Telegram bot

Set the token in `.env` and start the bot:

```bash
python -m ayman_os_agent.telegram_bot
```

The bot features:
- Interactive command menu (shows automatically when typing `/`)
- `/summary` — ملخص دراسة اليوم والتوصيات
- `/risk` — المواد الأكثر خطورة وأولوية
- `/sheet` — قراءة ملخص بيانات ورقة الدراسة
- `/report` — عرض تقرير المتابعة
- `/sendreport` — إرسال التقرير اليومي للوالد بالبريد
- `/appt` — عرض المواعيد أو إضافتها (`/appt list` أو `/appt مراجعة 2026-09-17 09:00`)
- `/ai` — التحدث مع الذكاء الاصطناعي (Gemini أو Bedrock)
- `/status` — عرض حالة النظام والملفات
- Free-form conversation: أي سؤال أو رسالة يتم الإجابة عليها تلقائياً.
- Built-in HTTP health check for cloud deployments (Railway/Render) on `$PORT`.

## Daily report sender

To generate and send a daily parent report automatically:

```bash
python send_daily_report.py
```

## Daily study commands

Useful commands for the workbook-backed study flow:

```bash
python -m ayman_os_agent.agent --sheet
python -m ayman_os_agent.agent --risk
python -m ayman_os_agent.agent --summary
python -m ayman_os_agent.agent "today summary"
python -m ayman_os_agent.agent "check risk"
```

On Windows, you can also schedule it with Task Scheduler once you set `PARENT_EMAIL`, `SMTP_*`, and `TELEGRAM_*` environment variables.

## AWS Bedrock and Gemini

Use `AI_BACKEND=gemini` for Gemini, `AI_BACKEND=bedrock` for Bedrock, or
`AI_BACKEND=auto` to prefer Bedrock and fall back to Gemini.

Set your credentials and optional model before using the AI features:

```bash
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
export AWS_BEDROCK_MODEL="anthropic.claude-3-haiku-20240307-v1:0"
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-3.6-flash"
```

## Install as a package

```bash
python -m pip install .
```

Then run:

```bash
ayman-os-agent --help
ayman-os-agent-bot
```
