from pyrogram import Client, filters
from pyrogram.types import Message

from Romeo import SUDO_USER
from config import *

R = "ROMEOBOT COMMAND"

@Client.on_message(filters.command(["help"], "."))
async def help(client: Client, message: Message):
    C = "https://telegra.ph//file/5467954d1156db5032062.jpg"
    CD = """
   ROMEOBOT HELP MENU
________________________________
           BOT
`.alive` - chek bot alive or not
`.ping` - chek bot ping
`.restart` - restart the bot
`.help` - To get commands

           BROADCAST
`.gcast` [text/reply] - Sending Global Broadcast messages to all groups.
`.gucast` [text/reply] - Sending Global Broadcast messages to all incoming Private Massages.        

           CLONE
`.clone` - reply_message for clone I'd
`.revert` - reply_message to cloner to get back

           EMOJI
`.emoji` - .emoji (name)
`.cmoji` - .cmoji (emoji or text) (name)

           HANG
 `.hang` - .hang (integer)       

           INVITE
 `.invitesall` - .invitesall @groupusername

           RAID 
`.raid` - .raid (count) (username or reply_message)
`.dmraid` - .dmraid (count) (username or reply_message)
`.replyraid` - .replyraid (username or reply_message)
`.lraid` - .lraid (count) (username or reply_message)
`.dmlraid` - .dmlraid (count) (username or reply_message)
`.psm` - .psm (count) for po*n spam

           SPAM
`.spam` - .spam (count) (message)
`.sspam` - .sspam (count) (reply_media)
`.delayspam` - .delayspam (time in second) (count) (text)

           TAGGER
 `.all` - .all (message) - to start usertagger
`.cancel` - to stop tagger

            TELEGRAPH
`.tm` - .tm (reply to any media) - to create teligraph link                
"""
    await message.delete()
    await message.reply_photo(photo=C, caption=R)
