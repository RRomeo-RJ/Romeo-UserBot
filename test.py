import os
import sys
import asyncio
import logging
from random import choice
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MULTI-DISPATCHER")

# ==================== CONFIGURATION ====================
API_ID = int(os.getenv("API_ID", "10796618"))
API_HASH = os.getenv("API_HASH", "4e4b20b4e1e40c90fcb1a7658c800150")
ALIVE_PIC = os.getenv("ALIVE_PIC", "https://telegra.ph/file/a62b9c7d9848afde0569e.jpg")

BOT_TOKENS = [
    "8722343571:AAGb0-cVV3UIlICubXrBQkNgey-ia4lC_hk",
    "8683176658:AAHD6qzboGWR3pD4yr3ODQg1pzopX4gVvk4",
]

SUDO_USERS = [5368154755, 7595462949, 8288876886]

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB Limit

# Global Queue & Download State Tracker
# Structure: {chat_id: [{"title": str, "file": str, "is_video": bool, "is_temp": bool, "message_ref": Message}]}
MUSIC_QUEUE = {}
DOWNLOADING_STATE = {}

# ==================== DATA LISTS FOR RAIDS & SPAM ====================
RAID = [
    "CHUTIYE TERI MAA KI CHUT ME MERA LUND", "TERI BEHEN KA BHOSDA", "RANDI KE BACHE", 
    "TERI MAA KA BHOSDA", "MADARCHOD", "BETICHOD", "TERI MAA KI CHUT", "NAALI KE KEEDE"
]
LOVE = [
    "I LOVE YOU JAAN", "MERI JAAN HO TUM", "BABU I LOVE YOU", "MISS YOU JAAN", 
    "Sona I Love You", "Jaanu meri jaan", "Tum meri ho"
]
PORM = [
    "https://telegra.ph/file/02525126831006900f86d.mp4",
    "https://telegra.ph/file/206a233c829e24876356a.mp4"
]

# States for Reply Raid & Love Raid: {bot_id: {chat_id: [user_ids]}}
RR_STATE = {}
RLR_STATE = {}

# ==================== ROMEO MULTI-BOT DISPATCHER ====================

class RomeoManager:
    def __init__(self):
        self.registered_handlers = []
        self.active_clients = []
        self.call_clients = {}  # {client_instance: pytgcalls_instance}

    def on_message(self, custom_filters=None):
        def decorator(func):
            self.registered_handlers.append((func, custom_filters))
            return func
        return decorator

    def apply_handlers_to_client(self, client: Client):
        for func, custom_filters in self.registered_handlers:
            if custom_filters is not None:
                client.add_handler(MessageHandler(func, custom_filters))
            else:
                client.add_handler(MessageHandler(func))

    async def start_all(self, tokens, api_id, api_hash):
        self.active_clients.clear()
        self.call_clients.clear()
        
        for i, token in enumerate(tokens, 1):
            if not token.strip():
                continue
            try:
                client = Client(
                    name=f"romeo_bot_session_{i}",
                    api_id=api_id,
                    api_hash=api_hash,
                    bot_token=token.strip(),
                    in_memory=True
                )
                
                self.apply_handlers_to_client(client)
                await client.start()
                self.active_clients.append(client)
                
                # Setup PyTgCalls & Stream End Listener
                pytgcalls_app = PyTgCalls(client)
                
                @pytgcalls_app.on_stream_end()
                async def stream_end_handler(_, update):
                    await handle_next_track(client, pytgcalls_app, update.chat_id)
                
                await pytgcalls_app.start()
                self.call_clients[client] = pytgcalls_app
                
                me = await client.get_me()
                logger.info(f"✅ Bot #{i} Active with Advanced Music Engine: @{me.username}")
            except Exception as e:
                logger.error(f"❌ Failed to start bot index {i}: {e}")
                
        return self.active_clients

    async def stop_all(self):
        for client, pytgcalls_app in self.call_clients.items():
            try:
                await pytgcalls_app.stop()
            except Exception as e:
                logger.warning(f"Error stopping PyTgCalls: {e}")
                
        for client in self.active_clients:
            try:
                await client.stop()
            except Exception as e:
                logger.warning(f"Error stopping client: {e}")
                
        self.active_clients.clear()
        self.call_clients.clear()
        logger.info("🛑 Multi-bot system shut down.")

romeo = RomeoManager()

# ==================== HELPER & QUEUE ENGINE ====================

async def resolve_target_chat(bot: Client, message: Message):
    args = message.text.split()
    if len(args) > 1 and (args[1].startswith("@") or args[1].lstrip("-").isdigit()):
        target_str = args[1]
        try:
            chat = await bot.get_chat(target_str)
            return chat
        except Exception as e:
            await message.reply_text(f"❌ Target group resolve nahi ho saka `{target_str}`: `{e}`")
            return None
    return message.chat

async def verify_vc_permissions(bot: Client, chat_id: int) -> bool:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        if member.status.value == "administrator":
            privileges = member.privileges
            if privileges and privileges.can_manage_video_chats:
                return True
        return False
    except Exception:
        return False

async def safe_file_cleanup(file_path: str, is_temp: bool):
    """Clean temp files to optimize storage"""
    if is_temp and file_path and os.path.exists(file_path) and "helper/Audio" not in file_path:
        try:
            os.remove(file_path)
            logger.info(f"🗑️ Deleted temp file: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")

async def predownload_next_track(bot: Client, chat_id: int):
    """Lazy download: Downloads ONLY the next queued track in background"""
    queue = MUSIC_QUEUE.get(chat_id, [])
    if len(queue) > 1:
        next_item = queue[1]
        if next_item.get("is_temp") and not next_item.get("downloaded_path") and next_item.get("media_msg"):
            if DOWNLOADING_STATE.get(chat_id):
                return
            DOWNLOADING_STATE[chat_id] = True
            try:
                logger.info(f"📥 Pre-downloading next track for chat {chat_id}...")
                path = await bot.download_media(next_item["media_msg"])
                next_item["downloaded_path"] = path
            except Exception as e:
                logger.error(f"Failed pre-downloading: {e}")
            finally:
                DOWNLOADING_STATE[chat_id] = False

async def handle_next_track(bot: Client, pytgcalls_app: PyTgCalls, chat_id: int):
    """Auto-plays next track or leaves VC if queue is empty"""
    queue = MUSIC_QUEUE.get(chat_id, [])
    
    if queue:
        # Finish current song -> Cleanup temp file
        finished_item = queue.pop(0)
        curr_path = finished_item.get("downloaded_path") or finished_item.get("file")
        await safe_file_cleanup(curr_path, finished_item.get("is_temp", False))

    if not queue:
        # Queue empty -> Auto Leave VC
        try:
            await pytgcalls_app.leave_group_call(chat_id)
            logger.info(f"🛑 Queue finished. Left VC in chat {chat_id}")
        except Exception:
            pass
        MUSIC_QUEUE.pop(chat_id, None)
        return

    # Play Next Track
    next_item = queue[0]
    next_path = next_item.get("downloaded_path")
    
    if not next_path and next_item.get("is_temp") and next_item.get("media_msg"):
        # Download if not pre-downloaded
        next_path = await bot.download_media(next_item["media_msg"])
        next_item["downloaded_path"] = next_path
    elif not next_path:
        next_path = next_item.get("file")

    is_video = next_item.get("is_video", False)
    stream = AudioVideoPiped(next_path) if is_video else AudioPiped(next_path)

    try:
        await pytgcalls_app.change_stream(chat_id, stream)
        # Trigger background download for the upcoming song
        asyncio.create_task(predownload_next_track(bot, chat_id))
    except Exception as e:
        logger.error(f"Error playing next stream in {chat_id}: {e}")
        await handle_next_track(bot, pytgcalls_app, chat_id)

# ==================== PUBLIC BASIC COMMANDS (NO ADMIN NEEDED) ====================

@romeo.on_message(filters.command("start", ["/", "."]))
async def start_cmd(bot: Client, message: Message):
    me = await bot.get_me()
    caption = (
        f"**🌟 Welcome to Multi-Bot Assistant (@{me.username}) 🌟**\n\n"
        f"🤖 **Status:** Online & Ready!\n"
        f"👤 **Bot Name:** {me.first_name}\n"
        f"⚡ **Engine:** Romeo Multi-Bot Dispatcher\n\n"
        f"Commands janne ke liye `/help` use karein."
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Support Group", url="https://t.me/RomeoBot_op")],
        [InlineKeyboardButton("📢 Updates Channel", url="https://t.me/Romeo_op")]
    ])
    
    try:
        await message.reply_photo(photo=ALIVE_PIC, caption=caption, reply_markup=buttons)
    except Exception:
        await message.reply_text(caption, reply_markup=buttons)

@romeo.on_message(filters.command("help", ["/", "."]))
async def help_cmd(bot: Client, message: Message):
    help_text = (
        "**📖 Romeo Multi-Bot Ultimate Guide 📖**\n\n"
        "**───────── BASIC COMMANDS ─────────**\n"
        "• `/start` , `/alive` , `/ping` , `/help` , `/queue` \n\n"

        "**───────── MUSIC CONTROLS (Sudo) ─────────**\n"
        "• `/play [target]` , `/skip [target]` , `/pause [target]` \n"
        "• `/resume [target]` , `/leavevc [target]` , `/clearqueue [target]` \n\n"

        "**───────── MASS DESTRUCTION (Sudo) ─────────**\n"
        "• `/banall [target]` → Group ke sabhi members ko ban karein.\n\n"

        "**───────── SPAM & RAID (Sudo) ─────────**\n"
        "• `/spam <count>` → Reply to media/text to spam.\n"
        "• `/raid <count> <user>` → User ko gaali raid karne ke liye.\n"
        "• `/lraid <count> <user>` → User ko love raid karne ke liye.\n"
        "• `/psm <count>` → Adult video spam karne ke liye.\n\n"

        "**───────── REPLY RAID (Sudo) ─────────**\n"
        "• `/rr <user/reply>` → Auto-reply raid (Gaali) activate karein.\n"
        "• `/drr` → Reply raid band karein.\n"
        "• `/rlr <user/reply>` → Auto-reply love raid (Pyaar) activate karein.\n"
        "• `/drlr` → Love reply raid band karein.\n"
        "📝 *Note: Agar dono active hain to 2 msg jayenge (1 gaali, 1 pyaar). Sudo ko sirf pyaar jayega.*\n\n"

        "**───────── PROFILE SETUP (Sudo) ─────────**\n"
        "• `.setname <Name>` , `.setbio <Bio>` , `.setdesc <Desc>` , `.setpic` \n\n"
        "💡 **Targeting Rule:** Command ke aage `@group` ya `groupID` lene par us target group me kaam hoga. Agar nahi doge toh CURRENT group me action hoga!"
    )
    await message.reply_text(help_text)

@romeo.on_message(filters.command("alive", ["/", "."]) & filters.user(SUDO_USERS))
async def alive_cmd(bot: Client, message: Message):
    me = await bot.get_me()
    await message.reply_text(f"✨ **Bot Active:** @{me.username}\n👤 **Name:** {me.first_name}")

@romeo.on_message(filters.command("ping", ["/", "."]))
async def ping_cmd(bot: Client, message: Message):
    await message.reply_text("🏓 Pong!")

@romeo.on_message(filters.command(["queue", "q"], ["/", "."]))
async def show_queue_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return
    
    queue = MUSIC_QUEUE.get(target_chat.id, [])
    if not queue:
        return await message.reply_text(f"📭 Queue khali hai `{target_chat.title if hasattr(target_chat, 'title') else target_chat.id}` me.")

    text = f"**📋 Music Queue - {target_chat.title if hasattr(target_chat, 'title') else target_chat.id}**\n\n"
    text += f"▶️ **Now Playing:** `{queue[0]['title']}`\n\n"

    if len(queue) > 1:
        text += "📑 **Up Next in Queue:**\n"
        for i, item in enumerate(queue[1:10], 1):
            text += f"`{i}.` {item['title']}\n"
        if len(queue) > 10:
            text += f"\n➕ {len(queue) - 10} aur songs queued hain."

    await message.reply_text(text)

# ==================== ADVANCED VC CONTROLS (ADMIN CHECKED) ====================

@romeo.on_message(filters.command(["play", "vcplay"], ["/", "."]) & filters.user(SUDO_USERS))
async def play_vc_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return

    # Admin Guard Check
    is_admin = await verify_vc_permissions(bot, target_chat.id)
    if not is_admin:
        return await message.reply_text(
            f"⚠️ **Pehle mujhe Group me Admin banao!**\n\n"
            f"Bot ko `{target_chat.title if hasattr(target_chat, 'title') else target_chat.id}` me **Admin** banao "
            f"aur permission do:\n• `Manage Video Chats` (Manage Voice Chats)"
        )

    pytgcalls_app = romeo.call_clients.get(bot)
    if not pytgcalls_app:
        return await message.reply_text("❌ PyTgCalls instance missing.")

    reply = message.reply_to_message
    item_data = {}

    # 1. Reply to Media Case
    if reply and (reply.audio or reply.video or reply.voice or reply.document):
        media = reply.audio or reply.video or reply.voice or reply.document
        
        # 200 MB Safety Check
        if getattr(media, "file_size", 0) > MAX_FILE_SIZE:
            return await message.reply_text("❌ **File Size Limit Exceeded!**\n\nFile 200MB se kam honi chahiye.")

        title = getattr(media, "file_name", None) or "Telegram Media Track"
        is_video = bool(reply.video or (reply.document and "video" in str(getattr(reply.document, "mime_type", ""))))
        
        item_data = {
            "title": title,
            "media_msg": reply,
            "downloaded_path": None,
            "is_video": is_video,
            "is_temp": True
        }

    # 2. Plain /play Case (Default Stored File)
    else:
        default_path = "./helper/Audio/B1.mp3"
        if not os.path.exists(default_path):
            return await message.reply_text(f"❌ Default audio missing at `{default_path}`.")
        
        item_data = {
            "title": "Default Asset Track",
            "file": default_path,
            "downloaded_path": default_path,
            "is_video": False,
            "is_temp": False
        }

    if target_chat.id not in MUSIC_QUEUE:
        MUSIC_QUEUE[target_chat.id] = []

    queue = MUSIC_QUEUE[target_chat.id]
    queue.append(item_data)

    # If already playing -> Add to queue
    if len(queue) > 1:
        pos = len(queue) - 1
        # Pre-download next song in background if this is index 1
        asyncio.create_task(predownload_next_track(bot, target_chat.id))
        return await message.reply_text(f"✅ **Queued in `{target_chat.title}`**\n📌 **Position:** #{pos} | `{item_data['title']}`")

    # If first song -> Download & Play
    sent = await message.reply_text("📥 **Song load ho raha hai...**")
    
    if item_data.get("is_temp"):
        downloaded = await bot.download_media(item_data["media_msg"])
        item_data["downloaded_path"] = downloaded
    else:
        downloaded = item_data["file"]

    stream = AudioVideoPiped(downloaded) if item_data["is_video"] else AudioPiped(downloaded)

    try:
        await pytgcalls_app.join_group_call(target_chat.id, stream)
        me = await bot.get_me()
        await sent.edit(f"🎶 **@{me.username} joined VC & playing in `{target_chat.title}`!**\n🎵 `{item_data['title']}`")
    except Exception as e:
        queue.pop(0)
        await safe_file_cleanup(downloaded, item_data.get("is_temp", False))
        await sent.edit(f"❌ **Error joining VC:** `{e}`")

@romeo.on_message(filters.command(["skip", "vcskip"], ["/", "."]) & filters.user(SUDO_USERS))
async def skip_vc_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return

    is_admin = await verify_vc_permissions(bot, target_chat.id)
    if not is_admin:
        return await message.reply_text("⚠️ **Pehle mujhe Group me Admin banao (Manage Voice Chats permission)!**")

    pytgcalls_app = romeo.call_clients.get(bot)
    queue = MUSIC_QUEUE.get(target_chat.id, [])

    if not queue:
        return await message.reply_text("📭 Queue me koi song nahi hai.")

    await message.reply_text(f"⏭️ **Instant Skipping in `{target_chat.title}`...**")
    await handle_next_track(bot, pytgcalls_app, target_chat.id)

@romeo.on_message(filters.command(["pause", "vcpause"], ["/", "."]) & filters.user(SUDO_USERS))
async def pause_vc_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return
    
    is_admin = await verify_vc_permissions(bot, target_chat.id)
    if not is_admin:
        return await message.reply_text("⚠️ **Pehle mujhe Group me Admin banao (Manage Voice Chats permission)!**")

    pytgcalls_app = romeo.call_clients.get(bot)
    if pytgcalls_app:
        try:
            await pytgcalls_app.pause_stream(target_chat.id)
            await message.reply_text(f"⏸️ **VC Stream Paused in `{target_chat.title}`.**")
        except Exception as e:
            await message.reply_text(f"⚠️ **Error pausing VC:** `{e}`")

@romeo.on_message(filters.command(["resume", "vcresume"], ["/", "."]) & filters.user(SUDO_USERS))
async def resume_vc_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return

    is_admin = await verify_vc_permissions(bot, target_chat.id)
    if not is_admin:
        return await message.reply_text("⚠️ **Pehle mujhe Group me Admin banao (Manage Voice Chats permission)!**")

    pytgcalls_app = romeo.call_clients.get(bot)
    if pytgcalls_app:
        try:
            await pytgcalls_app.resume_stream(target_chat.id)
            await message.reply_text(f"▶️ **VC Stream Resumed in `{target_chat.title}`.**")
        except Exception as e:
            await message.reply_text(f"⚠️ **Error resuming VC:** `{e}`")

@romeo.on_message(filters.command(["leavevc", "stopvc"], ["/", "."]) & filters.user(SUDO_USERS))
async def leave_vc_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return

    pytgcalls_app = romeo.call_clients.get(bot)
    
    # Cleanup temp files in queue
    queue = MUSIC_QUEUE.get(target_chat.id, [])
    for item in queue:
        path = item.get("downloaded_path") or item.get("file")
        await safe_file_cleanup(path, item.get("is_temp", False))

    MUSIC_QUEUE.pop(target_chat.id, None)

    if pytgcalls_app:
        try:
            await pytgcalls_app.leave_group_call(target_chat.id)
            await message.reply_text(f"🛑 **VC Leave kar diya aur Queue clear kar di `{target_chat.title}` me.**")
        except Exception as e:
            await message.reply_text(f"⚠️ **Error leaving VC:** `{e}`")

@romeo.on_message(filters.command(["clearqueue", "cqueue"], ["/", "."]) & filters.user(SUDO_USERS))
async def clear_queue_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return

    queue = MUSIC_QUEUE.get(target_chat.id, [])
    if not queue:
        return await message.reply_text("📭 Queue pehle se khali hai.")

    # Keep current song, delete remaining queued items and temp files
    current = queue[0]
    to_delete = queue[1:]
    
    for item in to_delete:
        path = item.get("downloaded_path") or item.get("file")
        await safe_file_cleanup(path, item.get("is_temp", False))

    MUSIC_QUEUE[target_chat.id] = [current]
    await message.reply_text(f"🗑️ **Queued songs clear kar diye gaye `{target_chat.title}` me (Current playing song chhod kar).**")

# ==================== MASS PROFILE CUSTOMIZATION (SUDO) ====================

@romeo.on_message(filters.command(["setname", "changename"], ["/", "."]) & filters.user(SUDO_USERS))
async def changename_cmd(bot: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `.setname <Naya Naam>`")
    new_name = message.text.split(None, 1)[1]
    success_count = sum(1 for c in romeo.active_clients if await safe_set_name(c, new_name))
    await message.reply_text(f"✅ Display name updated on {success_count}/{len(romeo.active_clients)} bots.")

async def safe_set_name(client, name):
    try:
        await client.set_my_name(name)
        return True
    except Exception:
        return False

@romeo.on_message(filters.command(["setbio", "changebio"], ["/", "."]) & filters.user(SUDO_USERS))
async def changebio_cmd(bot: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `.setbio <Naya Bio>`")
    new_bio = message.text.split(None, 1)[1]
    success_count = 0
    for client in romeo.active_clients:
        try:
            await client.set_my_short_description(new_bio)
            success_count += 1
        except Exception:
            pass
    await message.reply_text(f"✅ Bio updated on {success_count}/{len(romeo.active_clients)} bots.")

@romeo.on_message(filters.command(["setdesc", "setdescription"], ["/", "."]) & filters.user(SUDO_USERS))
async def changedesc_cmd(bot: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ **Usage:** `.setdesc <Naya Description>`")
    new_desc = message.text.split(None, 1)[1]
    success_count = 0
    for client in romeo.active_clients:
        try:
            await client.set_my_description(new_desc)
            success_count += 1
        except Exception:
            pass
    await message.reply_text(f"✅ Description updated on {success_count}/{len(romeo.active_clients)} bots.")

@romeo.on_message(filters.command(["setpic", "setphoto"], ["/", "."]) & filters.user(SUDO_USERS))
async def changepic_cmd(bot: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        return await message.reply_text("⚠️ Photo par reply karke `.setpic` bhejo.")

    op = await message.reply_text("🔄 **Photo download karke sabhi bots par DP lagayi ja rahi hai...**")
    photo_file = await bot.download_media(message.reply_to_message.photo)
    success_count = 0

    for client in romeo.active_clients:
        try:
            await client.set_profile_photo(photo=photo_file)
            success_count += 1
        except Exception:
            pass

    if os.path.exists(photo_file):
        os.remove(photo_file)

    await op.edit(f"✅ **Profile Photo {success_count}/{len(romeo.active_clients)} bots par update ho gayi!**")

# ==================== MASS DESTRUCTION COMMANDS (SUDO) ====================


@romeo.on_message(filters.command("banall", ["/", "."]) & filters.user(SUDO_USERS))
async def banall_cmd(bot: Client, message: Message):
    target_chat = await resolve_target_chat(bot, message)
    if not target_chat: return
    me = await bot.get_me()
    member = await bot.get_chat_member(target_chat.id, me.id)
    if not (member.privileges and member.privileges.can_restrict_members):
        return await message.reply_text(f"❌ **Ban permission nahi hai `{target_chat.title}` mein.**")
    sent = await message.reply_text(f"🚀 **Magic Started in `{target_chat.title}`...**")
    ban_count = 0
    async for member in bot.get_chat_members(target_chat.id):
        if member.user.id in SUDO_USERS or member.user.is_self: continue
        try:
            await bot.ban_chat_member(target_chat.id, member.user.id)
            ban_count += 1
        except Exception: continue
    await sent.edit(f"✅ **Banall Completed!**\nTotal Banned: `{ban_count}` members in `{target_chat.title}`.")
# ==================== SPAM COMMAND ====================
@romeo.on_message(filters.command(["spam", "s"], ["/", "."]) & filters.user(SUDO_USERS))
async def spam_cmd(bot: Client, message: Message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text("⚠️ **Usage:**\n1. Reply to any media: `.spam 10`\n2. Direct text: `.spam 10 Hello`")
    try:
        count = int(args[1])
    except ValueError:
        return await message.reply_text("❌ **Count number hona chahiye!** (Example: .spam 10)")
    
    await message.delete()
    if message.reply_to_message:
        reply = message.reply_to_message
        for _ in range(count):
            try:
                await reply.copy(message.chat.id) # Sticker, Video, Photo sab copy hoga
                await asyncio.sleep(0.1)
            except Exception: break
    elif len(args) > 2:
        spam_text = message.text.split(None, 2)[2] # ".spam 10 hlo" -> "hlo" lega
        for _ in range(count):
            try:
                await bot.send_message(message.chat.id, spam_text)
                await asyncio.sleep(0.1)
            except Exception: break
    else:
        await bot.send_message(message.chat.id, "❌ **Kucch toh do spam karne ke liye!**")

# ==================== RAID & LRAID COMMANDS ====================
@romeo.on_message(filters.command(["raid", "r"], ["/", "."]) & filters.user(SUDO_USERS))
async def raid_cmd(bot: Client, message: Message):
    try:
        parts = message.text.split()
        count = int(parts[1]) if len(parts) > 1 else 5
        target = parts[2] if len(parts) > 2 else None
    except:
        return await message.reply_text("⚠️ **Usage:** `/raid <count> <username/reply>`")
    user = None
    if message.reply_to_message: user = message.reply_to_message.from_user
    elif target:
        try: user = await bot.get_users(target)
        except: return await message.reply_text("❌ User nahi mila.")
    if not user: return await message.reply_text("⚠️ User mention karo ya reply karo.")
    if user.id in SUDO_USERS: return await message.reply_text("❌ Sudo users par raid nahi hogi.")
    await message.delete()
    mention = f"@{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
    for _ in range(count):
        await bot.send_message(message.chat.id, f"{mention} {choice(RAID)}")
        await asyncio.sleep(1)

@romeo.on_message(filters.command(["lraid", "lr"], ["/", "."]) & filters.user(SUDO_USERS))
async def lraid_cmd(bot: Client, message: Message):
    try:
        parts = message.text.split()
        count = int(parts[1]) if len(parts) > 1 else 5
        target = parts[2] if len(parts) > 2 else None
    except:
        return await message.reply_text("⚠️ **Usage:** `/lraid <count> <username/reply>`")
    user = None
    if message.reply_to_message: user = message.reply_to_message.from_user
    elif target:
        try: user = await bot.get_users(target)
        except: return await message.reply_text("❌ User nahi mila.")
    if not user: return await message.reply_text("⚠️ User mention karo ya reply karo.")
    await message.delete()
    mention = f"@{user.username}" if user.username else f"[{user.first_name}](tg://user?id={user.id})"
    for _ in range(count):
        await bot.send_message(message.chat.id, f"{mention} {choice(LOVE)}")
        await asyncio.sleep(1)

# ==================== PORN SPAM COMMAND ====================
@romeo.on_message(filters.command(["psm", "porm", "pornspam"], ["/", "."]) & filters.user(SUDO_USERS))
async def psm_cmd(bot: Client, message: Message):
    try:
        count = int(message.command[1]) if len(message.command) > 1 else 5
    except: count = 5
    await message.delete()
    for _ in range(count):
        try:
            await bot.send_video(message.chat.id, video=choice(PORM))
            await asyncio.sleep(1)
        except: break

# ==================== REPLY RAID & LOVE RAID ACTIVATION ====================
@romeo.on_message(filters.command(["rr", "replyraid"], ["/", "."]) & filters.user(SUDO_USERS))
async def activate_rr(bot: Client, message: Message):
    user = (message.reply_to_message.from_user if message.reply_to_message else None)
    if not user and len(message.command) > 1:
        try: user = await bot.get_users(message.command[1])
        except: return await message.reply_text("❌ User nahi mila.")
    if not user: return await message.reply_text("⚠️ Reply karo ya username do.")
    bot_id = (await bot.get_me()).id
    if bot_id not in RR_STATE: RR_STATE[bot_id] = {}
    if message.chat.id not in RR_STATE[bot_id]: RR_STATE[bot_id][message.chat.id] = []
    RR_STATE[bot_id][message.chat.id].append(user.id)
    await message.reply_text(f"✅ **Reply Raid Activated** for {user.mention}!")

@romeo.on_message(filters.command(["drr", "stoprr"], ["/", "."]) & filters.user(SUDO_USERS))
async def stop_rr(bot: Client, message: Message):
    bot_id = (await bot.get_me()).id
    if bot_id in RR_STATE and message.chat.id in RR_STATE[bot_id]:
        RR_STATE[bot_id].pop(message.chat.id)
        await message.reply_text("❌ **Reply Raid Deactivated!**")

@romeo.on_message(filters.command(["rlr", "replyloveraid"], ["/", "."]) & filters.user(SUDO_USERS))
async def activate_rlr(bot: Client, message: Message):
    user = (message.reply_to_message.from_user if message.reply_to_message else None)
    if not user and len(message.command) > 1:
        try: user = await bot.get_users(message.command[1])
        except: return await message.reply_text("❌ User nahi mila.")
    if not user: return await message.reply_text("⚠️ Reply karo ya username do.")
    bot_id = (await bot.get_me()).id
    if bot_id not in RLR_STATE: RLR_STATE[bot_id] = {}
    if message.chat.id not in RLR_STATE[bot_id]: RLR_STATE[bot_id][message.chat.id] = []
    RLR_STATE[bot_id][message.chat.id].append(user.id)
    await message.reply_text(f"💕 **Reply Love Raid Activated** for {user.mention}!")

@romeo.on_message(filters.command(["drlr", "stoprlr"], ["/", "."]) & filters.user(SUDO_USERS))
async def stop_rlr(bot: Client, message: Message):
    bot_id = (await bot.get_me()).id
    if bot_id in RLR_STATE and message.chat.id in RLR_STATE[bot_id]:
        RLR_STATE[bot_id].pop(message.chat.id)
        await message.reply_text("❌ **Reply Love Raid Deactivated!**")

# ==================== GENERAL HANDLER (UPDATED LOGIC) ====================
@romeo.on_message(filters.incoming & filters.group, group=10)
async def rr_logic_handler(bot: Client, message: Message):
    if not message.from_user: return
    user_id = message.from_user.id
    bot_id = (await bot.get_me()).id
    
    is_sudo = user_id in SUDO_USERS

    # Tagging Logic for Reply Raid
    mention = f"@{message.from_user.username}" if message.from_user.username else f"[{message.from_user.first_name}](tg://user?id={message.from_user.id})"
    
    # Check karein ki raid active hai ya nahi
    rr_active = (bot_id in RR_STATE and message.chat.id in RR_STATE[bot_id] and user_id in RR_STATE[bot_id][message.chat.id])
    rlr_active = (bot_id in RLR_STATE and message.chat.id in RLR_STATE[bot_id] and user_id in RLR_STATE[bot_id][message.chat.id])
    
    # 1. Agar Normal Raid active hai AUR user Sudo nahi hai -> Gaali bhejo
    if rr_active and not is_sudo:
        await message.reply_text(f"{mention} {choice(RAID)}")
    
    # 2. Agar Love Raid active hai -> Pyaar bhejo (Sudo ho ya na ho, pyaar jayega)
    if rlr_active:
        await message.reply_text(f"{mention} {choice(LOVE)}")

# ==================== MAIN LOADER INTEGRATION ====================

async def start_bot():
    bots = await romeo.start_all(BOT_TOKENS, API_ID, API_HASH)
    if not bots:
        raise Exception("No valid bot tokens initialized.")
    first_bot = await bots[0].get_me()
    return first_bot.username

async def stop_bot():
    await romeo.stop_all()

# ==================== STANDALONE RUNNER ====================

if __name__ == "__main__":
    async def main_standalone():
        try:
            bots = await romeo.start_all(BOT_TOKENS, API_ID, API_HASH)
            print("=" * 50)
            print(f"🚀 Romeo Multi-Bot Advanced Music Engine Active ({len(bots)} Bots Active)")
            print("=" * 50)
            await idle()
        finally:
            await romeo.stop_all()

    try:
        asyncio.run(main_standalone())
    except KeyboardInterrupt:
        print("\n👋 System shut down.")
