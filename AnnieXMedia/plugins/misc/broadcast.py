# Authored By Certified Coders © 2025
"""
Enhanced Broadcast Module
========================
Features:
- Text broadcast
- Image/Photo broadcast  
- Inline button support (URL buttons)
- Interactive setup process

Commands:
- /broadcast - Original broadcast command
- /newbroadcast - Show broadcast setup guide
- /setbroadcast - Set broadcast content (reply to message)
- /startbroadcast - Execute the broadcast

Button Format:
TEXT | Button1:URL1 | Button2:URL2

Example:
"📢 Announcement! Join us | Support:t.me/support | Channel:t.me/channel"
"""
import asyncio
import json

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from AnnieXMedia import app
from AnnieXMedia.misc import SUDOERS
from AnnieXMedia.utils.database import (
    get_active_chats,
    get_authuser_names,
    get_client,
    get_served_chats,
    get_served_users,
)
from AnnieXMedia.utils.decorators.language import language
from AnnieXMedia.utils.formatters import alpha_to_int
from config import adminlist

IS_BROADCASTING = False


def parse_broadcast_buttons(text: str):
    """Helper to parse buttons from text in format: TEXT | Button:URL"""
    if "|" not in text:
        return text, None
    
    parts = text.split("|")
    main_text = parts[0].strip()
    buttons = []
    
    for part in parts[1:]:
        part = part.strip()
        if ":" in part:
            try:
                btn_text, url = part.split(":", 1)
                buttons.append(InlineKeyboardButton(btn_text.strip(), url=url.strip()))
            except:
                continue
    
    if not buttons:
        return main_text, None
        
    # Arrange buttons in rows of 2
    keyboard = []
    for i in range(0, len(buttons), 2):
        keyboard.append(buttons[i:i+2])
        
    return main_text, InlineKeyboardMarkup(keyboard)


@app.on_message(filters.command("broadcast") & SUDOERS)
@language
async def braodcast_message(client, message, _):
    global IS_BROADCASTING
    
    # Flags to handle
    pin_flag = "-pin" in message.text
    nobot_flag = "-nobot" in message.text
    pinloud_flag = "-pinloud" in message.text
    assistant_flag = "-assistant" in message.text
    user_flag = "-user" in message.text
    
    reply_markup = None
    query = ""
    
    if message.reply_to_message:
        x = message.reply_to_message.id
        y = message.chat.id
        # If user provided buttons in the command while replying
        if len(message.command) > 1:
            cmd_text = message.text.split(None, 1)[1]
            # Remove flags from cmd_text for button parsing
            for flag in ["-pin", "-nobot", "-pinloud", "-assistant", "-user"]:
                cmd_text = cmd_text.replace(flag, "")
            _, reply_markup = parse_broadcast_buttons(cmd_text)
    else:
        if len(message.command) < 2:
            return await message.reply_text(_["broad_2"])
        
        query = message.text.split(None, 1)[1]
        # Remove flags for parsing
        clean_query = query
        for flag in ["-pin", "-nobot", "-pinloud", "-assistant", "-user"]:
            clean_query = clean_query.replace(flag, "")
            
        if clean_query.strip() == "":
            return await message.reply_text(_["broad_8"])
            
        query, reply_markup = parse_broadcast_buttons(clean_query)

    IS_BROADCASTING = True
    await message.reply_text(_["broad_1"])

    if not nobot_flag:
        sent = 0
        pin = 0
        schats = await get_served_chats()
        
        for chat in schats:
            chat_id = int(chat["chat_id"])
            try:
                if message.reply_to_message:
                    if reply_markup:
                        # If we have custom buttons, we must copy instead of forward
                        m = await message.reply_to_message.copy(
                            chat_id,
                            reply_markup=reply_markup
                        )
                    else:
                        m = await app.forward_messages(chat_id, y, x)
                else:
                    m = await app.send_message(
                        chat_id, 
                        text=query,
                        reply_markup=reply_markup
                    )
                
                if pin_flag:
                    try:
                        await m.pin(disable_notification=True)
                        pin += 1
                    except:
                        pass
                elif pinloud_flag:
                    try:
                        await m.pin(disable_notification=False)
                        pin += 1
                    except:
                        pass
                
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                continue
                
        try:
            await message.reply_text(_["broad_3"].format(sent, pin))
        except:
            pass

    if user_flag:
        susr = 0
        susers = await get_served_users()
        for user in susers:
            user_id = int(user["user_id"])
            try:
                if message.reply_to_message:
                    if reply_markup:
                        await message.reply_to_message.copy(
                            user_id,
                            reply_markup=reply_markup
                        )
                    else:
                        await app.forward_messages(user_id, y, x)
                else:
                    await app.send_message(
                        user_id, 
                        text=query,
                        reply_markup=reply_markup
                    )
                susr += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                pass
        try:
            await message.reply_text(_["broad_4"].format(susr))
        except:
            pass

    if assistant_flag:
        aw = await message.reply_text(_["broad_5"])
        text = _["broad_6"]
        from AnnieXMedia.core.userbot import assistants

        for num in assistants:
            sent = 0
            client = await get_client(num)
            async for dialog in client.get_dialogs():
                try:
                    if message.reply_to_message:
                        # Assistants don't support copy() as easily as app, 
                        # and usually don't send inline buttons. 
                        # We stick to forward/send for assistants.
                        await client.forward_messages(dialog.chat.id, y, x)
                    else:
                        await client.send_message(dialog.chat.id, text=query)
                    sent += 1
                    await asyncio.sleep(3)
                except FloodWait as fw:
                    flood_time = int(fw.value)
                    if flood_time > 200:
                        continue
                    await asyncio.sleep(flood_time)
                except:
                    continue
            text += _["broad_7"].format(num, sent)
        try:
            await aw.edit_text(text)
        except:
            pass
            
    IS_BROADCASTING = False


@app.on_message(filters.command("newbroadcast") & SUDOERS)
@language
async def new_broadcast_message(client, message, _):
    """Enhanced broadcast with text, image, and inline buttons support"""
    global IS_BROADCASTING
    
    # Send configuration panel
    await message.reply_text(
        "📢 <b>Broadcast Configuration Panel</b>\n\n"
        "Please reply to this message with your broadcast content:\n\n"
        "• <b>Text only:</b> Just send the text\n"
        "• <b>With image:</b> Send image with caption\n"
        "• <b>With buttons:</b> Use format:\n"
        "  <code>TEXT | BUTTON_TEXT:URL | BUTTON_TEXT:URL</code>\n\n"
        "<b>Example with buttons:</b>\n"
        "<code>Hello everyone | Support:t.me/support | Channel:t.me/channel</code>\n\n"
        "<b>Example with image and buttons:</b>\n"
        "Send image with caption: <code>Hello | Support:t.me/support</code>",
        parse_mode="html"
    )


@app.on_message(filters.command("setbroadcast") & SUDOERS)
@language
async def set_broadcast_content(client, message, _):
    """Set broadcast content interactively"""
    global IS_BROADCASTING
    
    if IS_BROADCASTING:
        return await message.reply_text("⚠️ A broadcast is already in progress!")
    
    # Check if user replied to a message
    if not message.reply_to_message:
        return await message.reply_text(
            "❌ Please reply to a message with /setbroadcast\n\n"
            "• Reply to text for text-only broadcast\n"
            "• Reply to image/photo for image broadcast\n"
            "• The message should contain buttons in this format:\n"
            "  <code>Your message text | Button1:URL1 | Button2:URL2</code>",
            parse_mode="html"
        )
    
    replied = message.reply_to_message
    
    # Extract content
    text = replied.text or replied.caption or ""
    photo_id = None
    
    # Check if it's a photo
    if replied.photo:
        photo_id = replied.photo.file_id
        if not text:
            text = "📢 <b>Important Announcement</b>"
    
    # Parse buttons from text
    buttons = []
    if "|" in text:
        parts = text.split("|")
        text = parts[0].strip()
        
        # Parse button parts
        for part in parts[1:]:
            part = part.strip()
            if ":" in part:
                btn_text, url = part.split(":", 1)
                buttons.append([
                    InlineKeyboardButton(btn_text.strip(), url=url.strip())
                ])
    
    # Create keyboard if buttons exist
    reply_markup = None
    if buttons:
        # Arrange buttons in rows of 2
        arranged_buttons = []
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            arranged_buttons.append([btn[0] for btn in row])
        reply_markup = InlineKeyboardMarkup(arranged_buttons)
    
    # Send confirmation
    if photo_id:
        await message.reply_photo(
            photo=photo_id,
            caption=text,
            reply_markup=reply_markup,
            parse_mode="html"
        )
        await message.reply_text(
            "✅ <b>Broadcast content set!</b>\n\n"
            "Now use /startbroadcast to send this to all users/chats.\n\n"
            "<b>Options:</b>\n"
            "• <code>/startbroadcast</code> - Send to all chats\n"
            "• <code>/startbroadcast -user</code> - Send to users only\n"
            "• <code>/startbroadcast -pin</code> - Pin in chats\n"
            "• <code>/startbroadcast -pinloud</code> - Pin with notification",
            parse_mode="html"
        )
    else:
        await message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode="html"
        )
        await message.reply_text(
            "✅ <b>Broadcast content set!</b>\n\n"
            "Now use /startbroadcast to send this to all users/chats.\n\n"
            "<b>Options:</b>\n"
            "• <code>/startbroadcast</code> - Send to all chats\n"
            "• <code>/startbroadcast -user</code> - Send to users only\n"
            "• <code>/startbroadcast -pin</code> - Pin in chats\n"
            "• <code>/startbroadcast -pinloud</code> - Pin with notification",
            parse_mode="html"
        )
    
    # Store broadcast content temporarily
    app.BROADCAST_CONTENT = {
        "text": text,
        "photo_id": photo_id,
        "reply_markup": reply_markup,
        "message_id": replied.id,
        "chat_id": replied.chat.id
    }


@app.on_message(filters.command("startbroadcast") & SUDOERS)
@language
async def start_broadcast(client, message, _):
    """Start the broadcast with stored content"""
    global IS_BROADCASTING
    
    if not hasattr(app, 'BROADCAST_CONTENT') or not app.BROADCAST_CONTENT:
        return await message.reply_text(
            "❌ No broadcast content set!\n\n"
            "Use /setbroadcast first by replying to a message."
        )
    
    if IS_BROADCASTING:
        return await message.reply_text("⚠️ A broadcast is already in progress!")
    
    IS_BROADCASTING = True
    content = app.BROADCAST_CONTENT
    
    # Get broadcast flags
    flags = message.text.split()[1:] if len(message.command) > 1 else []
    pin_flag = "-pin" in flags or "-pinloud" in flags
    user_flag = "-user" in flags
    
    await message.reply_text("📢 <b>Starting broadcast...</b>\n\nPlease wait while I send the message to all users/chats.")
    
    # Broadcast to chats
    if "-nobot" not in flags:
        sent = 0
        pin = 0
        chats = []
        schats = await get_served_chats()
        for chat in schats:
            chats.append(int(chat["chat_id"]))
        
        for i in chats:
            try:
                if content["photo_id"]:
                    m = await app.send_photo(
                        i,
                        photo=content["photo_id"],
                        caption=content["text"],
                        reply_markup=content["reply_markup"],
                        parse_mode="html"
                    )
                else:
                    m = await app.send_message(
                        i,
                        text=content["text"],
                        reply_markup=content["reply_markup"],
                        parse_mode="html"
                    )
                
                if pin_flag:
                    try:
                        disable_notification = "-pin" in flags
                        await m.pin(disable_notification=disable_notification)
                        pin += 1
                    except:
                        pass
                
                sent += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                continue
        
        try:
            await message.reply_text(
                f"✅ <b>Broadcast completed!</b>\n\n"
                f"📊 <b>Stats:</b>\n"
                f"• Sent to <code>{sent}</code> chats\n"
                f"• Pinned in <code>{pin}</code> chats"
            )
        except:
            pass
    
    # Broadcast to users
    if user_flag:
        susr = 0
        served_users = []
        susers = await get_served_users()
        for user in susers:
            served_users.append(int(user["user_id"]))
        
        for i in served_users:
            try:
                if content["photo_id"]:
                    await app.send_photo(
                        i,
                        photo=content["photo_id"],
                        caption=content["text"],
                        reply_markup=content["reply_markup"],
                        parse_mode="html"
                    )
                else:
                    await app.send_message(
                        i,
                        text=content["text"],
                        reply_markup=content["reply_markup"],
                        parse_mode="html"
                    )
                susr += 1
                await asyncio.sleep(0.2)
            except FloodWait as fw:
                flood_time = int(fw.value)
                if flood_time > 200:
                    continue
                await asyncio.sleep(flood_time)
            except:
                pass
        
        try:
            await message.reply_text(
                f"✅ <b>User broadcast completed!</b>\n\n"
                f"📊 Sent to <code>{susr}</code> users"
            )
        except:
            pass
    
    IS_BROADCASTING = False
    # Clear stored content
    app.BROADCAST_CONTENT = None


async def auto_clean():
    while not await asyncio.sleep(10):
        try:
            served_chats = await get_active_chats()
            for chat_id in served_chats:
                if chat_id not in adminlist:
                    adminlist[chat_id] = []
                    async for user in app.get_chat_members(
                        chat_id, filter=ChatMembersFilter.ADMINISTRATORS
                    ):
                        if getattr(user.privileges, 'can_manage_video_chats', False):
                            adminlist[chat_id].append(user.user.id)
                    authusers = await get_authuser_names(chat_id)
                    for user in authusers:
                        user_id = await alpha_to_int(user)
                        adminlist[chat_id].append(user_id)
        except:
            continue


asyncio.create_task(auto_clean())
