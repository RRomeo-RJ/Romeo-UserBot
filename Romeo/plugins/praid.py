import asyncio
import random
import asyncio
import time
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram import filters, Client

from Romeo.helper.data import *
from Romeo import SUDO_USER

@Client.on_message(filters.command(["pornspam", "psm"], "."))
async def prns(client: Client, message: Message):
    r = await message.reply_text("`Processing..`")
    quantity = message.command[1]
    failed = 0
    quantity = int(quantity)
    await r.delete()
    if int(message.chat.id) in GROUP:
        await message.reply_text("`You Cannot Pornspam In Developer Chats!`")
        return
    for _ in range(quantity):
        try:
            file = random.choice(PORM)            
            await client.send_video(chat_id=message.chat.id, video=file)
        except FloodWait as e:
            await asyncio.sleep(e.x)
