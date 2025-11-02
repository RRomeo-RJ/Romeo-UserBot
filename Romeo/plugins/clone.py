import os
import json
from pyrogram import *
from pyrogram.types import *
from Romeo.helper.basic import edit_or_reply, get_text, get_user
from Romeo import SUDO_USER

OWNER = os.environ.get("OWNER", None)
BIO = os.environ.get("BIO", "RomeoBot User")  # Fallback bio (jab original bio na mile)
ORIGINAL_DATA_FILE = "Original.json"


def load_original_data():
    """Load original data from JSON file (agar exist kare to)"""
    if os.path.exists(ORIGINAL_DATA_FILE):
        try:
            with open(ORIGINAL_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_original_data(data):
    """Save original data to JSON file"""
    with open(ORIGINAL_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def backup_original_profile(client: Client, user_id: int):
    """Backup original profile data before cloning"""
    try:
        # Get original data
        me = await client.get_me()
        my_chat = await client.get_chat(me.id)
        
        original_data = {
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "bio": my_chat.bio or "",  # Original bio save karo (empty ho sakta hai)
            "username": me.username or "",
            "photo_count": 0,
            "photos": []
        }
        
        # Save all profile photos
        photo_paths = []
        photos = [p async for p in client.get_chat_photos("me")]
        original_data["photo_count"] = len(photos)
        
        for idx, photo in enumerate(photos):
            photo_path = f"original_photo_{user_id}_{idx}.jpg"
            await client.download_media(photo.file_id, file_name=photo_path)
            photo_paths.append(photo_path)
        
        original_data["photos"] = photo_paths
            
        # Load existing data
        all_data = load_original_data()
        
        # Save data with user_id as key
        all_data[str(user_id)] = original_data
        
        # Save to file (ab create hoga agar nahi hai to)
        save_original_data(all_data)
        
        return True
    except Exception as e:
        print(f"Error backing up profile: {e}")
        return False


async def try_set_username(client: Client, base_username: str):
    """Try to set username with last letter repetition"""
    if not base_username:
        return None
    
    # Try with 1 extra last letter
    try:
        modified_username = base_username + base_username[-1]
        await client.set_username(modified_username)
        return modified_username
    except:
        pass
    
    # Try with 3 extra last letters
    try:
        modified_username = base_username + (base_username[-1] * 3)
        await client.set_username(modified_username)
        return modified_username
    except:
        pass
    
    return None


@Client.on_message(filters.command("clone", "."))
async def clone(client: Client, message: Message):
    text = get_text(message)
    op = await message.edit_text("`🔍 Processing...`")
    
    userk = get_user(message, text)[0]
    user_ = await client.get_users(userk)
    
    if not user_:
        await op.edit("`❌ Whom should I clone?`")
        return

    # Get current user's ID (original client)
    me = await client.get_me()
    my_id = me.id
    
    # Backup original profile data (sirf pehli baar)
    all_data = load_original_data()
    if str(my_id) not in all_data:
        await op.edit("`📦 Backing up your original profile...`")
        backup_success = await backup_original_profile(client, my_id)
        
        if not backup_success:
            await op.edit("`❌ Failed to backup original profile!`")
            return
    
    # Clone the target user
    await op.edit("`🔄 Cloning profile...`")
    
    try:
        get_bio = await client.get_chat(user_.id)
        f_name = user_.first_name or "User"
        l_name = user_.last_name or ""
        c_bio = get_bio.bio or ""  # Target ka bio (empty bhi ho sakta hai)
        target_username = user_.username or ""
        
        # Download and set ALL profile photos
        await op.edit("`📸 Downloading profile pictures...`")
        target_photos = [p async for p in client.get_chat_photos(user_.id)]
        
        downloaded_photos = []
        for idx, photo in enumerate(target_photos):
            photo_path = f"clone_temp_{user_.id}_{idx}.jpg"
            await client.download_media(photo.file_id, file_name=photo_path)
            downloaded_photos.append(photo_path)
        
        # Set all photos (reverse order to maintain sequence)
        if downloaded_photos:
            await op.edit("`🖼️ Setting profile pictures...`")
            for photo_path in reversed(downloaded_photos):
                await client.set_profile_photo(photo=photo_path)
                # Delete temp file
                if os.path.exists(photo_path):
                    os.remove(photo_path)

        # Update profile (bio empty bhi ho sakta hai)
        await op.edit("`✏️ Updating profile details...`")
        await client.update_profile(
            first_name=f_name,
            last_name=l_name,
            bio=c_bio,  # Jo bhi mile wo use karo
        )
        
        # Try to set username with modifications
        username_status = "❌ Not available"
        if target_username:
            await op.edit("`🔧 Setting username...`")
            new_username = await try_set_username(client, target_username)
            if new_username:
                username_status = f"✅ @{new_username}"
        
        await message.edit(
            f"**✅ Successfully Cloned!**\n\n"
            f"**👤 Name:** `{f_name} {l_name}`\n"
            f"**📝 Bio:** `{c_bio[:50] if c_bio else 'None'}...`\n"
            f"**📸 Photos:** `{len(downloaded_photos)} copied`\n"
            f"**🔗 Username:** {username_status}\n\n"
            f"_Your original data is safely backed up!_"
        )
    except Exception as e:
        await op.edit(f"`❌ Error: {str(e)}`")


@Client.on_message(filters.command("revert", "."))
async def revert(client: Client, message: Message):
    await message.edit("`🔄 Reverting to original profile...`")
    
    # Get current user's ID
    me = await client.get_me()
    my_id = str(me.id)
    
    # Load original data
    all_data = load_original_data()
    
    if my_id not in all_data:
        await message.edit(
            "`⚠️ No backup found! Using fallback values...`"
        )
        # Fallback to environment variables (jab backup nahi mila)
        fallback_bio = BIO  # Tab use karo BIO variable
        await client.update_profile(
            first_name=OWNER if OWNER else "User",
            last_name="",
            bio=fallback_bio,
        )
        # Delete all current photos
        photos = [p async for p in client.get_chat_photos("me")]
        if photos:
            photo_ids = [p.file_id for p in photos]
            await client.delete_profile_photos(photo_ids)
        
        await message.edit("`✅ Reverted to fallback settings!`")
        return
    
    try:
        # Get saved original data
        original_data = all_data[my_id]
        
        await message.edit("`🗑️ Removing cloned data...`")
        
        # Delete ALL current photos (cloned ones)
        current_photos = [p async for p in client.get_chat_photos("me")]
        if current_photos:
            photo_ids = [p.file_id for p in current_photos]
            await client.delete_profile_photos(photo_ids)
        
        await message.edit("`🖼️ Restoring original photos...`")
        
        # Restore original photos (in reverse order)
        if original_data.get("photos"):
            for photo_path in reversed(original_data["photos"]):
                if os.path.exists(photo_path):
                    await client.set_profile_photo(photo=photo_path)
                    # Delete the backup file after restoring
                    os.remove(photo_path)
        
        await message.edit("`✏️ Restoring profile details...`")
        
        # Restore profile (original bio use karo, empty bhi ho sakta hai)
        await client.update_profile(
            first_name=original_data.get("first_name", "User"),
            last_name=original_data.get("last_name", ""),
            bio=original_data.get("bio", ""),  # Original bio (empty bhi ho sakta hai)
        )
        
        # Restore original username
        if original_data.get("username"):
            try:
                await client.set_username(original_data["username"])
            except:
                pass
        
        await message.edit(
            f"**✅ Successfully Reverted!**\n\n"
            f"**👤 Name:** `{original_data.get('first_name')} {original_data.get('last_name', '')}`\n"
            f"**📝 Bio:** `{original_data.get('bio', 'None')[:50]}`\n"
            f"**📸 Photos:** `{original_data.get('photo_count', 0)} restored`\n"
            f"**🔗 Username:** `@{original_data.get('username', 'None')}`\n\n"
            f"_Welcome back to your original profile!_"
        )
        
        # Remove data from JSON (auto-cleanup)
        del all_data[my_id]
        save_original_data(all_data)
        
        await message.edit(
            f"**✅ Successfully Reverted!**\n\n"
            f"**👤 Name:** `{original_data.get('first_name')} {original_data.get('last_name', '')}`\n"
            f"**📝 Bio:** `{original_data.get('bio', 'None')[:50]}`\n"
            f"**📸 Photos:** `{original_data.get('photo_count', 0)} restored`\n"
            f"**🔗 Username:** `@{original_data.get('username', 'None')}`\n\n"
            f"_✨ Backup data cleaned automatically!_"
        )
        
    except Exception as e:
        await message.edit(f"`❌ Error while reverting: {str(e)}`")
