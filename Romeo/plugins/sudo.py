from pyrogram import filters, Client
from pyrogram.types import Message
from Romeo import SUDO_USER

@Client.on_message(filters.command(["addsudo", "asd"], "."))
async def addsudo(client: Client, message: Message):
    try:
        if not message.reply_to_message:
            if len(message.command) != 2:
                await message.reply_text("Reply to a user's message or give username/user_id.")
                return
            user = message.text.split(None, 1)[1]
            if "@" in user:
                user = user.replace("@", "")
            user = await client.get_users(user)
            if user.id in SUDO_USER:
                await message.reply_text("{0} is already a sudo user.".format(user.mention))
                return
            SUDO_USER.append(user.id)
            await message.reply_text("Added **{0}** to Sudo Users.".format(user.mention))

        if message.reply_to_message.from_user.id in SUDO_USER:
            await message.reply_text("{0} is already a sudo user.".format(message.reply_to_message.from_user.mention))
            return
        SUDO_USER.append(message.reply_to_message.from_user.id)
        await message.reply_text("Added **{0}** to Sudo Users.".format(message.reply_to_message.from_user.mention))
    except Exception as e:
        await message.reply_text(f"**ERROR:** `{e}`")
        return

@Client.on_message(filters.command(["delsudo", "rmsudo", "rsd"], "."))
async def rmsudo(client: Client, message: Message):
    try:
        if not message.reply_to_message:
            if len(message.command) != 2:
                await message.reply_text("Reply to a user's message or give username/user_id.")
                return
            user = message.text.split(None, 1)[1]
            if "@" in user:
                user = user.replace("@", "")
            user = await client.get_users(user)
            if user.id not in SUDO_USER:
                await message.reply_text("**{0}** is not a part of Bot's Sudo.".format(user.mention))
                return 
            SUDO_USER.remove(user.id)
            await message.reply_text("Removed **{0}** from Bot's Sudo User".format(user.mention))
        user_id = message.reply_to_message.from_user.id
        if user_id not in SUDO_USER:
            return await message.reply_text("**{0}** is not a part of Bot's Sudo.".format(message.reply_to_message.from_user.mention))
        SUDO_USER.remove(user_id)
        await message.reply_text("Removed **{0}** from Bot's Sudo User".format(message.reply_to_message.from_user.mention))
    except Exception as e:
        await message.reply_text(f"**ERROR:** `{e}`")
        return


@Client.on_message(filters.command(["sudolist", "sdl", "lsd"], "."))
async def sudolist(client: Client, message: Message):
    users = SUDO_USER
    ex = await message.edit_text("`Processing...`")
    if not users:
        await ex.edit("No Users have been set yet")
        return
    sudo_list = "**Sudo Users:**\n"
    count = 0
    for i in users:
        count += 1
        sudo_list += f"**{count} -** `{i}`\n"
    await ex.edit(sudo_list)
    return 
