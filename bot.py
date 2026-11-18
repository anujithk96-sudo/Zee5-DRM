import logging
import os
import time
import asyncio
import yt_dlp
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ലോഗിങ് സെറ്റ് ചെയ്യുക
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Required environment variables (configure these in your hosting platform)
def load_config():
    required = ("API_ID", "API_HASH", "BOT_TOKEN")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )
    try:
        api_id = int(os.environ["API_ID"])
    except ValueError as exc:
        raise RuntimeError("API_ID must be an integer") from exc
    return api_id, os.environ["API_HASH"], os.environ["BOT_TOKEN"]

API_ID, API_HASH, BOT_TOKEN = load_config()

# വലിയ URL-കളും യൂസർ ഡാറ്റകളും സേവ് ചെയ്തു വെക്കാനുള്ള ഡിക്ഷണറികൾ
USER_URLS = {}
USER_THUMBNAILS = {}
USER_STATES = {}

# Pyrogram ക്ലയന്റ് initialization
app = Client(
    "zee5_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# വീഡിയോയുടെ ഡ്യൂറേഷൻ (Duration) കണ്ടുപിടിക്കാൻ
def get_video_duration(file_path):
    try:
        parser = createParser(file_path)
        if parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("duration"):
                return int(metadata.get("duration").seconds)
    except Exception:
        pass
    return 0

# പ്രോഗ്രസ് ബാർ ഉണ്ടാക്കാൻ
def get_progress_bar(percentage):
    try:
        pct = float(str(percentage).replace('%', '').strip())
    except:
        pct = 0.0
    completed = int(pct // 10)
    remaining = 10 - completed
    return "█" * completed + "░" * remaining

# ലൈവ് പ്രോഗ്രസ് ബാർ ഹുക്ക്
def get_progress_hook(client, message, title="Downloading"):
    last_update_time = 0
    def progress_hook(d):
        nonlocal last_update_time
        if d['status'] == 'downloading':
            current_time = time.time()
            if current_time - last_update_time > 3:
                percentage = d.get('_percent_str', '0%').strip()
                speed = d.get('_speed_str', 'N/A').strip()
                eta = d.get('_eta_str', 'N/A').strip()
                bar = get_progress_bar(percentage)
                try:
                    asyncio.run_coroutine_threadsafe(
                        message.edit_text(
                            f"📥 {title}...\n\n"
                            f"[{bar}] {percentage}\n"
                            f"🚀 Speed: {speed}\n"
                            f"⏱️ ETA: {eta}"
                        ),
                        client.loop
                    )
                except Exception:
                    pass
                last_update_time = current_time
    return progress_hook

# യൂസർ സെറ്റിംഗ്സ് കീബോർഡ്
def build_user_settings_keyboard(user_id):
    has_thumb = "Yes ✅" if user_id in USER_THUMBNAILS else "No ❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🖼️ Thumbnail Set: {has_thumb}", callback_data="set_thumb")],
        [InlineKeyboardButton("👀 View Thumbnail", callback_data="view_thumb")],
        [InlineKeyboardButton("🗑️ Remove Thumbnail", callback_data="remove_thumb")]
    ])

# /start കമാൻഡ്
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text(
        "👋 Hello! Welcome to Zee5 Downloader Bot.\n\n"
        "Send any Zee5 link with `-n custom_name` for renaming, and download as Audio or Video!",
        reply_markup=build_user_settings_keyboard(message.from_user.id)
    )

# /settings കമാൻഡ്
@app.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    await message.reply_text(
        "⚙️ **User Settings**\n\nManage your custom thumbnail here:",
        reply_markup=build_user_settings_keyboard(message.from_user.id)
    )

# സെറ്റിംഗ്സ് ബട്ടൺ കോൾബാക്കുകൾ
@app.on_callback_query(filters.regex("^(set_thumb|view_thumb|remove_thumb)$"))
async def settings_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if data == "set_thumb":
        USER_STATES[user_id] = "waiting_for_thumb"
        await callback_query.message.reply_text("📸 Please send the photo you want to set as custom thumbnail.")
    elif data == "view_thumb":
        if user_id in USER_THUMBNAILS and os.path.exists(USER_THUMBNAILS[user_id]):
            await client.send_photo(chat_id=user_id, photo=USER_THUMBNAILS[user_id], caption="🖼️ Your current custom thumbnail.")
        else:
            await callback_query.answer("❌ No custom thumbnail set yet!", show_alert=True)
    elif data == "remove_thumb":
        if user_id in USER_THUMBNAILS:
            if os.path.exists(USER_THUMBNAILS[user_id]):
                os.remove(USER_THUMBNAILS[user_id])
            del USER_THUMBNAILS[user_id]
            await callback_query.answer("🗑️ Custom thumbnail removed successfully!", show_alert=True)
        else:
            await callback_query.answer("❌ No custom thumbnail to remove!", show_alert=True)
        try:
            await callback_query.message.edit_reply_markup(reply_markup=build_user_settings_keyboard(user_id))
        except:
            pass
    await callback_query.answer()

# Accept Zee5 canonical links and Zee5 OneLink short links.
def normalize_zee5_url(raw_url):
    raw_url = raw_url.strip().rstrip(".,)")
    parsed = urlparse(raw_url)
    host = (parsed.hostname or "").lower()
    allowed = host == "zee5.com" or host.endswith(".zee5.com") or host == "zee5.onelink.me"
    if parsed.scheme not in ("http", "https") or not allowed:
        raise ValueError("Please send a valid Zee5 URL or zee5.onelink.me short link.")
    if host == "zee5.onelink.me":
        # Resolve only the official Zee5 short-link host; reject redirects elsewhere.
        request = Request(raw_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=15) as response:
            final_url = response.geturl()
        final_host = (urlparse(final_url).hostname or "").lower()
        if not (final_host == "zee5.com" or final_host.endswith(".zee5.com")):
            raise ValueError("The short link did not redirect to an official Zee5 page.")
        return final_url
    return raw_url

# ഫോട്ടോയോ ലിങ്കോ ഇൻപുട്ട് എടുക്കുന്ന ഹാൻഡ്‌ലർ
@app.on_message(filters.private & ~filters.command(["start", "settings"]))
async def handle_user_inputs(client, message):
    user_id = message.from_user.id
    state = USER_STATES.get(user_id)

    if state == "waiting_for_thumb" and message.photo:
        os.makedirs("thumbnails", exist_ok=True)
        thumb_path = f"thumbnails/{user_id}.jpg"
        await message.download(file_name=thumb_path)
        USER_THUMBNAILS[user_id] = thumb_path
        USER_STATES[user_id] = None
        await message.reply_text("✅ Custom thumbnail saved successfully!", reply_markup=build_user_settings_keyboard(user_id))
        return

    text = message.text.strip() if message.text else ""
    if "zee5.com" in text.lower() or "zee5.onelink.me" in text.lower():
        parts = text.split("-n", 1)
        raw_url = parts[0].strip()
        custom_name = parts[1].strip() if len(parts) > 1 else None
        try:
            url = normalize_zee5_url(raw_url)
        except Exception as exc:
            await message.reply_text(f"❌ Link error: {exc}")
            return
        if custom_name:
            # Keep filenames safe across Linux/Windows filesystems.
            custom_name = "".join(
                ch for ch in custom_name if ch.isalnum() or ch in " ._-"
            ).strip(" .")[:100] or None

        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("http", "https") or not (
            host == "zee5.com" or host.endswith(".zee5.com")
        ):
            await message.reply_text("❌ Please send a valid https://www.zee5.com link.")
            return

        USER_URLS[user_id] = {"url": url, "custom_name": custom_name}
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎵 Extract MP3 Audio", callback_data="dl|audio|mp3")],
            [
                InlineKeyboardButton("📹 144p", callback_data="dl|video|144"),
                InlineKeyboardButton("📹 240p", callback_data="dl|video|240")
            ],
            [
                InlineKeyboardButton("📹 360p", callback_data="dl|video|360"),
                InlineKeyboardButton("📹 480p", callback_data="dl|video|480")
            ],
            [
                InlineKeyboardButton("📹 576p", callback_data="dl|video|576"),
                InlineKeyboardButton("📹 720p", callback_data="dl|video|720")
            ],
            [
                InlineKeyboardButton("📹 1080p", callback_data="dl|video|1080")
            ]
        ])
        await message.reply_text("📥 Zee5 link detected! Please select your required format:", reply_markup=keyboard)
    else:
        if not state:
            await message.reply_text("❌ Please send a valid Zee5 link with `-n custom_name` or use `/settings`.")

# ഡൗൺലോഡ് പ്രോസസ്സ് ഹാൻഡ്‌ലർ
@app.on_callback_query(filters.regex("^dl\|"))
async def download_media(client, callback_query: CallbackQuery):
    data_parts = callback_query.data.split("|")
    media_type = data_parts[1] 
    quality = data_parts[2]
    
    user_id = callback_query.from_user.id
    user_data = USER_URLS.get(user_id)

    if not user_data:
        await callback_query.message.edit_text("❌ Link expired. Please send the link again.")
        return

    url = user_data["url"]
    custom_name = user_data["custom_name"]

    if media_type == "audio":
        status_msg = await callback_query.message.edit_text("🎵 Extracting MP3 audio... Please wait...")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'progress_hooks': [get_progress_hook(client, status_msg, "Downloading Audio")],
            'geo_bypass': True,
        }
    else:
        status_msg = await callback_query.message.edit_text(f"📥 Downloading {quality}p video... Please wait...")
        ydl_opts = {
            'format': f'best[height<={quality}]/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'progress_hooks': [get_progress_hook(client, status_msg, f"Downloading {quality}p Video")],
            'geo_bypass': True,
        }

    # Reliability tuning for ordinary, non-DRM media supported by yt-dlp.
    ydl_opts.update({
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "file_access_retries": 3,
        "socket_timeout": 30,
        "continuedl": True,
        "overwrites": False,
        "concurrent_fragment_downloads": 4,
        "ignoreerrors": False,
    })

    # cookies.txt ഫയൽ ഉണ്ടെങ്കിൽ അത് കോൺഫിഗറേഷനിൽ ചേർക്കുന്നു
    if os.path.exists("cookies.txt"):
        ydl_opts['cookiefile'] = "cookies.txt"

    filename = None
    try:
        os.makedirs("downloads", exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # yt-dlp is synchronous; run it in a worker thread so the bot
            # can continue responding to other Telegram updates.
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            filename = ydl.prepare_filename(info)
            
            if media_type == "audio":
                filename = os.path.splitext(filename)[0] + ".mp3"

        if not filename or not os.path.exists(filename):
            raise Exception("Downloaded file not found!")

        dir_name, orig_filename = os.path.split(filename)
        name_part, ext = os.path.splitext(orig_filename)
        
        if custom_name:
            new_filename = os.path.join(dir_name, f"{custom_name}{ext}")
            os.rename(filename, new_filename)
            filename = new_filename

        await status_msg.edit_text("📤 Uploading to Telegram...")

        thumb_path = None
        if user_id in USER_THUMBNAILS and os.path.exists(USER_THUMBNAILS[user_id]):
            thumb_path = USER_THUMBNAILS[user_id]

        if media_type == "audio":
            await client.send_audio(
                chat_id=callback_query.message.chat.id,
                audio=filename,
                thumb=thumb_path,
                caption="🎵 Here is your Zee5 MP3 Audio!"
            )
        else:
            file_name = os.path.basename(filename)
            duration = get_video_duration(filename)

            await client.send_video(
                chat_id=callback_query.message.chat.id,
                video=filename,
                file_name=file_name,
                duration=duration,
                thumb=thumb_path,
                caption=f"📹 Here is your Zee5 Video ({quality}p)!"
            )

        await status_msg.delete()
        
        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        logger.exception("Media processing failed for user %s", user_id)
        try:
            error_text = str(e).replace("<", "[").replace(">", "]")[:700]
            lowered = error_text.lower()
            if "drm" in lowered or "widevine" in lowered or "license" in lowered:
                reason = ("This title appears to use DRM protection. This bot supports "
                          "only media that is legitimately downloadable without bypassing DRM.")
            else:
                reason = f"{error_text or 'Unknown extractor error'}\nCheck hosting logs for the full traceback."
            await status_msg.edit_text(f"❌ Download failed: {reason}")
        except Exception:
            pass

if __name__ == "__main__":
    logger.info("Starting Zee5 link bot...")
    app.run()
