# Zee5 Telegram Bot — startup fixes

## Requirements
- Python 3.10+
- FFmpeg installed and available on PATH
- Telegram API credentials from https://my.telegram.org

## Install
```bash
pip install -r requirements.txt
```

## Configure environment variables
Set these as environment variables in your hosting provider (do not commit them):
- `API_ID` — Telegram API ID (integer)
- `API_HASH` — Telegram API hash
- `BOT_TOKEN` — Telegram bot token from BotFather

## Run
```bash
python bot.py
```

The bot reports missing configuration clearly at startup. The download feature relies
on yt-dlp's normal supported extraction only; DRM-protected streams are not bypassed.
A valid Zee5 link may still be unavailable if the service does not expose a supported
non-DRM stream.
