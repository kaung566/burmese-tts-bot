cat << 'EOF' > app.py
import asyncio
import os
import time
import html
import logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import edge_tts

try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# စာလုံးရေ အများဆုံး ကန့်သတ်ချက်
MAX_CHARACTERS = 3000

# မဖြစ်မနေ Join ရမည့် Channel များ
REQUIRED_CHANNELS = [
    {"name": "📢 Channel (၁) Join ရန်", "username": "@movierecaps6", "url": "https://t.me/movierecaps6"},
    {"name": "📢 Channel (၂) Join ရန်", "username": "@movierecaps67", "url": "https://t.me/movierecaps67"},
]

VOICE_MODES = {
    "v1":  {"name": "🎙️ မောင်ဘကျော်",        "voice": "my-MM-ThihaNeural",                 "rate": "+18%", "pitch": "+0Hz"},
    "v2":  {"name": "🎙️ မယ်ဖွား",              "voice": "my-MM-NilarNeural",                 "rate": "+18%", "pitch": "+0Hz"},
    "v3":  {"name": "🎙️ မောင်ရွှေရိုး",          "voice": "it-IT-GiuseppeMultilingualNeural",  "rate": "+15%", "pitch": "+0Hz"},
    "v4":  {"name": "🎙️ မောင်သာဒင်",         "voice": "en-AU-WilliamMultilingualNeural",   "rate": "+15%", "pitch": "+0Hz"},
    "v5":  {"name": "🎙️ ဘိုးထွန်း",           "voice": "en-US-AndrewMultilingualNeural",    "rate": "+15%", "pitch": "+0Hz"},
    "v6":  {"name": "🎙️ မယ်သိင်္ဂီ",         "voice": "en-US-AvaMultilingualNeural",       "rate": "+15%", "pitch": "+0Hz"},
    "v7":  {"name": "🎙️ ဘသောင်း",              "voice": "en-US-BrianMultilingualNeural",     "rate": "+15%", "pitch": "+0Hz"},
    "v8":  {"name": "🎙️ မြသီ",              "voice": "en-US-EmmaMultilingualNeural",      "rate": "+15%", "pitch": "+0Hz"},
    "v9":  {"name": "🎙️ ဘညွန့်",              "voice": "fr-FR-RemyMultilingualNeural",      "rate": "+15%", "pitch": "+0Hz"},
    "v10": {"name": "🎙️ မယ်နု",              "voice": "fr-FR-VivienneMultilingualNeural",  "rate": "+15%", "pitch": "+0Hz"},
    "v11": {"name": "🎙️ မယ်စိန်",            "voice": "de-DE-SeraphinaMultilingualNeural", "rate": "+15%", "pitch": "+0Hz"},
    "v12": {"name": "🎙️ ဖိုးထောင်",             "voice": "de-DE-FlorianMultilingualNeural",   "rate": "+15%", "pitch": "+0Hz"},
    "v13": {"name": "🎙️ မယ်နန်း",             "voice": "pt-BR-ThalitaMultilingualNeural",   "rate": "+15%", "pitch": "+0Hz"},
    "v14": {"name": "🎙️ ကျော်စွာ",          "voice": "ko-KR-HyunsuMultilingualNeural",    "rate": "+15%", "pitch": "+0Hz"},
}

async def check_user_joined(user_id: int, bot) -> bool:
    """User သည် Channel (၂) ခုလုံး Join ထားခြင်း ရှိ/မရှိ စစ်ဆေးခြင်း"""
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["username"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.warning(f"Error checking membership for {ch['username']}: {e}")
            return False
    return True

def build_join_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([InlineKeyboardButton(ch["name"], url=ch["url"])])
    buttons.append([InlineKeyboardButton("🔄 Join ပြီးပါက ဤနေရာကိုနှိပ်ပါ", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)

def build_voice_keyboard(selected_v="v1"):
    buttons = []
    keys = list(VOICE_MODES.keys())
    for i in range(0, len(keys), 2):
        row = []
        for k in keys[i:i+2]:
            v_info = VOICE_MODES[k]
            name_clean = v_info['name'].replace("🎙️ ", "")
            mark = "✅ " if k == selected_v else "🎙️ "
            row.append(InlineKeyboardButton(f"{mark}{name_clean}", callback_data=f"sel_{k}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔊 လက်ရှိရွေးထားသော အသံကို စမ်းနားထောင်ရန်", callback_data="test_voice")])
    return InlineKeyboardMarkup(buttons)

def build_settings_keyboard(speed, pitch):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏪ Speed -10%", callback_data="speed_down"),
            InlineKeyboardButton(f"⚡ {speed:+d}%", callback_data="none"),
            InlineKeyboardButton("Speed +10% ⏩", callback_data="speed_up")
        ],
        [
            InlineKeyboardButton("🔉 Pitch -2Hz", callback_data="pitch_down"),
            InlineKeyboardButton(f"🎵 {pitch:+d}Hz", callback_data="none"),
            InlineKeyboardButton("Pitch +2Hz 🔊", callback_data="pitch_up")
        ],
        [
            InlineKeyboardButton("🎙️ အသံထုတ်မည်", callback_data="generate_audio")
        ]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Channel Join စစ်ဆေးခြင်း
    if not await check_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "⚠️ <b>Bot ကို အသုံးပြုရန် Channel များကို အရင် Join ပေးပါ</b>\n\n"
            "အောက်ပါ Channel (၂) ခုလုံးကို Join ပြီးမှသာ Bot ကို အသုံးပြုခွင့် ရရှိမည်ဖြစ်ပါသည်ခင်ဗျာ-",
            reply_markup=build_join_keyboard(),
            parse_mode="HTML"
        )
        return

    context.user_data.setdefault("voice", "v1")
    context.user_data.setdefault("speed", 0)
    context.user_data.setdefault("pitch", 0)

    welcome_text = (
        "🙏 <b>Burmese Text to speech tg bot မှ ကြိုဆိုပါတယ်</b> 🙏\n"
        "အသုံးပြုသူများ အားလုံး စိတ်ချမ်းသာ ကိုယ်ကျန်းမာစွာဖြင့် အဆင်ပြေကြပါစေခင်ဗျာ။ ✨\n\n"
        "👇 <b>အသံပုံစံ ကို ရွေးချယ်ပေးပါ-</b>"
    )
    await update.message.reply_text(
        welcome_text,
        reply_markup=build_voice_keyboard(context.user_data["voice"]),
        parse_mode="HTML"
    )

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if await check_user_joined(user_id, context.bot):
        await query.answer("✅ Channel များ Join ထားပြီးဖြစ်ပါသည်။ Bot ကို စတင်သုံးနိုင်ပါပြီ!", show_alert=True)
        context.user_data.setdefault("voice", "v1")
        context.user_data.setdefault("speed", 0)
        context.user_data.setdefault("pitch", 0)

        welcome_text = (
            "🙏 <b>Burmese Text to speech tg bot မှ ကြိုဆိုပါတယ်</b> 🙏\n"
            "Channel Join ခြင်း အောင်မြင်ပါသည်။ ✨\n\n"
            "👇 <b>အသံပုံစံ ကို ရွေးချယ်ပေးပါ-</b>"
        )
        await query.edit_message_text(
            welcome_text,
            reply_markup=build_voice_keyboard(context.user_data["voice"]),
            parse_mode="HTML"
        )
    else:
        await query.answer("❌ Channel (၂) ခုလုံးကို Join မထားသေးပါခင်ဗျာ။ အရင်ဆုံး Join ပေးပါ!", show_alert=True)

async def voice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not await check_user_joined(user_id, context.bot):
        await query.answer("⚠️ Channel များကို အရင် Join ပေးပါ!", show_alert=True)
        await query.message.reply_text(
            "⚠️ <b>Bot ကို အသုံးပြုရန် Channel များကို အရင် Join ပေးပါ</b>",
            reply_markup=build_join_keyboard(),
            parse_mode="HTML"
        )
        return

    await query.answer()
    data = query.data

    if data.startswith("sel_"):
        v_key = data.replace("sel_", "")
        context.user_data["voice"] = v_key
        v_name = VOICE_MODES[v_key]["name"].replace("🎙️ ", "")

        await query.edit_message_reply_markup(reply_markup=build_voice_keyboard(v_key))
        await query.message.reply_text(
            f"✅ <b>{html.escape(v_name)}</b> အသံကို ရွေးချယ်ပြီးပါပြီ။\n\n"
            f"📝 အသံပြောင်းလိုသော စာသား (Text) များကို ပို့ပေးပါခင်ဗျာ-\n"
            f"<i>(အများဆုံး စာလုံးရေ ၃၀၀၀ အထိ ပို့နိုင်ပါသည်)</i>",
            parse_mode="HTML"
        )

    elif data == "test_voice":
        v_key = context.user_data.get("voice", "v1")
        v_info = VOICE_MODES[v_key]
        name_clean = v_info["name"].replace("🎙️ ", "")
        sample_text = f"မင်္ဂလာပါ၊ ကျွန်တော်ကတော့ {name_clean} ဖြစ်ပါတယ်။ အသံကြည်လင်စွာ ထွက်ရှိနေပါပြီ။"

        user_speed = context.user_data.get("speed", 0)
        user_pitch = context.user_data.get("pitch", 0)

        base_rate = int(v_info["rate"].replace("%", ""))
        base_pitch = int(v_info["pitch"].replace("Hz", ""))

        rate_str = f"{base_rate + user_speed:+d}%"
        pitch_str = f"{base_pitch + user_pitch:+d}Hz"

        file_path = f"sample_{query.from_user.id}.mp3"
        communicate = edge_tts.Communicate(sample_text, v_info["voice"], rate=rate_str, pitch=pitch_str)
        await communicate.save(file_path)
        with open(file_path, "rb") as audio:
            await query.message.reply_audio(audio=audio, caption=f"🔊 စမ်းသပ်သံ: {name_clean}")
        if os.path.exists(file_path):
            os.remove(file_path)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Channel Join စစ်ဆေးခြင်း
    if not await check_user_joined(user_id, context.bot):
        await update.message.reply_text(
            "⚠️ <b>Bot ကို အသုံးပြုရန် Channel များကို အရင် Join ပေးပါ</b>",
            reply_markup=build_join_keyboard(),
            parse_mode="HTML"
        )
        return

    user_text = update.message.text.strip()
    text_length = len(user_text)

    # စာလုံးရေ ၃၀၀၀ ကန့်သတ်ချက် စစ်ဆေးခြင်း
    if text_length > MAX_CHARACTERS:
        await update.message.reply_text(
            f"❌ <b>စာလုံးရေ အကန့်အသတ် ကျော်လွန်နေပါသည်!</b>\n\n"
            f"• အများဆုံး ခွင့်ပြုထားသည့် စာလုံးရေ: <b>{MAX_CHARACTERS}</b> လုံး\n"
            f"• သင်ပေးပို့ထားသော စာလုံးရေ: <b>{text_length}</b> လုံး\n\n"
            f"⚠️ ကျေးဇူးပြု၍ စာသားကို <b>{MAX_CHARACTERS}</b> လုံးအောက် လျှော့ချပြီးမှ ပြန်လည် ပေးပို့ပေးပါခင်ဗျာ။",
            parse_mode="HTML"
        )
        return

    context.user_data["text"] = user_text
    context.user_data.setdefault("voice", "v1")
    context.user_data.setdefault("speed", 0)
    context.user_data.setdefault("pitch", 0)

    v_name = VOICE_MODES[context.user_data["voice"]]["name"].replace("🎙️ ", "")
    speed = context.user_data["speed"]
    pitch = context.user_data["pitch"]

    preview = user_text[:60] + "..." if len(user_text) > 60 else user_text
    safe_preview = html.escape(preview)
    safe_vname = html.escape(v_name)

    settings_msg = (
        f"📝 <b>စာသား လက်ခံရရှိပါပြီ!</b> ({text_length}/{MAX_CHARACTERS} လုံး)\n"
        f"<i>{safe_preview}</i>\n\n"
        f"⚙️ <b>အသံချိန်ညှိချက်များ ပြင်ဆင်ပါ-</b>\n"
        f"• လက်ရှိအသံ: <b>{safe_vname}</b>\n"
        f"• အမြန်နှုန်း အတိုးအလျှော့ (Speed): <code>{speed:+d}%</code>\n"
        f"• အသံအနိမ့်အမြင့် (Pitch): <code>{pitch:+d}Hz</code>\n\n"
        f"အဆင်ပြေပါက အောက်ပါ <b>[🎙️ အသံထုတ်မည်]</b> ခလုတ်ကို နှိပ်ပါ-"
    )
    await update.message.reply_text(
        settings_msg,
        reply_markup=build_settings_keyboard(speed, pitch),
        parse_mode="HTML"
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if not await check_user_joined(user_id, context.bot):
        await query.answer("⚠️ Channel များကို အရင် Join ပေးပါ!", show_alert=True)
        return

    data = query.data
    speed = context.user_data.get("speed", 0)
    pitch = context.user_data.get("pitch", 0)

    if data == "speed_up" and speed < 50:
        speed += 10
    elif data == "speed_down" and speed > -50:
        speed -= 10
    elif data == "pitch_up" and pitch < 10:
        pitch += 2
    elif data == "pitch_down" and pitch > -10:
        pitch -= 2
    elif data == "generate_audio":
        await query.answer()
        await start_audio_generation(query, context)
        return

    await query.answer()
    context.user_data["speed"] = speed
    context.user_data["pitch"] = pitch

    v_name = VOICE_MODES[context.user_data.get("voice", "v1")]["name"].replace("🎙️ ", "")
    user_text = context.user_data.get("text", "")
    preview = user_text[:60] + "..." if len(user_text) > 60 else user_text
    safe_preview = html.escape(preview)
    safe_vname = html.escape(v_name)

    new_msg = (
        f"📝 <b>စာသား လက်ခံရရှိပါပြီ!</b> ({len(user_text)}/{MAX_CHARACTERS} လုံး)\n"
        f"<i>{safe_preview}</i>\n\n"
        f"⚙️ <b>အသံချိန်ညှိချက်များ ပြင်ဆင်ပါ-</b>\n"
        f"• လက်ရှိအသံ: <b>{safe_vname}</b>\n"
        f"• အမြန်နှုန်း အတိုးအလျှော့ (Speed): <code>{speed:+d}%</code>\n"
        f"• အသံအနိမ့်အမြင့် (Pitch): <code>{pitch:+d}Hz</code>\n\n"
        f"အဆင်ပြေပါက အောက်ပါ <b>[🎙️ အသံထုတ်မည်]</b> ခလုတ်ကို နှိပ်ပါ-"
    )
    await query.edit_message_text(
        new_msg,
        reply_markup=build_settings_keyboard(speed, pitch),
        parse_mode="HTML"
    )

async def start_audio_generation(query, context):
    user_text = context.user_data.get("text", "")
    if not user_text:
        await query.message.reply_text("စာသား မရှိသေးပါ။ စာသား အရင် ပို့ပေးပါခင်ဗျာ။")
        return

    v_key = context.user_data.get("voice", "v1")
    v_info = VOICE_MODES[v_key]
    name_clean = v_info["name"].replace("🎙️ ", "")

    base_rate = int(v_info["rate"].replace("%", ""))
    base_pitch = int(v_info["pitch"].replace("Hz", ""))

    total_speed = base_rate + context.user_data.get("speed", 0)
    total_pitch = base_pitch + context.user_data.get("pitch", 0)

    rate_str = f"{total_speed:+d}%"
    pitch_str = f"{total_pitch:+d}Hz"

    start_time = time.time()
    stop_event = asyncio.Event()

    async def track_progress():
        stages = [
            (30, "[■■■□□□□□□□]"),
            (60, "[■■■■■■□□□□]"),
            (85, "[■■■■■■■■□□]"),
            (95, "[■■■■■■■■■□]"),
        ]
        idx = 0
        while not stop_event.is_set():
            elapsed = round(time.time() - start_time, 1)
            pct, bar = stages[min(idx, len(stages) - 1)]
            try:
                await query.edit_message_text(
                    f"🎙️ Audio: အသံထုတ်လုပ်နေပါသည်... ({elapsed}s)\n     {bar} {pct}%"
                )
            except Exception:
                pass
            if idx < len(stages) - 1:
                idx += 1
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1.2)
            except asyncio.TimeoutError:
                pass

    progress_task = asyncio.create_task(track_progress())
    out_file = f"voice_{query.from_user.id}.mp3"

    try:
        communicate = edge_tts.Communicate(user_text, v_info["voice"], rate=rate_str, pitch=pitch_str)
        await communicate.save(out_file)

        stop_event.set()
        await progress_task

        elapsed = round(time.time() - start_time, 1)
        await query.edit_message_text(f"🎙️ Audio: ✅ ပြီးပါပြီ ({elapsed}s)\n     [■■■■■■■■■■] 100%")

        with open(out_file, "rb") as audio:
            await query.message.reply_audio(
                audio=audio,
                title=f"TTS - {name_clean}",
                performer="Burmese Text to speech",
                caption=f"🎙️ အသံ: {name_clean} | Speed: {rate_str} | Pitch: {pitch_str}"
            )
        await query.message.reply_text(
            "🎉 <b>Burmese Text to speech bot</b> မှာ အသံထုတ်ရတာ အဆင်ပြေပါစေခင်ဗျာ။ 🙏✨\n"
            "နောက်ထပ် အသံထုတ်လိုပါက စာသားများကို ဆက်လက် ပို့ပေးနိုင်ပါသည်!",
            parse_mode="HTML"
        )
    except Exception as e:
        stop_event.set()
        await progress_task
        await query.message.reply_text(f"❌ အသံထုတ်ရာတွင် Error ဖြစ်ပွားပါသည်- {str(e)}")
    finally:
        if os.path.exists(out_file):
            os.remove(out_file)

# Render 24/7 သက်ရှိထင်ရှားရှိနေစေရန် Web Server
async def handle_ping(request):
    return web.Response(text="Bot is running 24/7!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is required.")

    await start_web_server()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(voice_callback, pattern="^(sel_|test_voice)"))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^(speed_|pitch_|generate_audio|none)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_bot())
EOF
