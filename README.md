# Zee5 Telegram Link Bot (improved reliability)

## Changes
- Accepts official `zee5.com` URLs and `zee5.onelink.me` short links.
- Resolves Zee5 short links and verifies that the final host remains an official Zee5 domain.
- Adds yt-dlp retry, timeout, resume, and fragment concurrency settings for media yt-dlp can legally access.
- Displays a clearer error when a title appears DRM-protected.
- Keeps boot-time validation for `API_ID`, `API_HASH`, and `BOT_TOKEN`.

## Important limitation
This bot does not bypass DRM, Widevine, subscription controls, or other access restrictions. Zee5 titles protected by DRM may not be downloadable with yt-dlp. Use Zee5's official offline/download feature where available, or test this bot only with media you are authorized to download and that is not DRM-protected.

## Setup
Set `API_ID`, `API_HASH`, and `BOT_TOKEN` as environment variables in your hosting platform. Install `requirements.txt` and the system package listed in `apt.txt` (FFmpeg).
