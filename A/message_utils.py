#!/usr/bin/env python3
from traceback import format_exc
from asyncio import sleep
from aiofiles.os import remove as aioremove
from random import choice as rchoice
from time import time
from re import match as re_match
from cryptography.fernet import InvalidToken

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaPhoto
from pyrogram.errors import (
    ReplyMarkupInvalid,
    FloodWait,
    PeerIdInvalid,
    ChannelInvalid,
    RPCError,
    UserNotParticipant,
    MessageNotModified,
    MessageEmpty,
    PhotoInvalidDimensions,
    WebpageCurlFailed,
    MediaEmpty,
)

from bot import (
    config_dict,
    user_data,
    categories_dict,
    bot_cache,
    LOGGER,
    bot_name,
    status_reply_dict,
    status_reply_dict_lock,
    Interval,
    bot,
    user,
    download_dict_lock,
)
from bot.helper.ext_utils.bot_utils import (
    get_readable_message,
    setInterval,
    sync_to_async,
    download_image_url,
    fetch_user_tds,
    fetch_user_dumps,
)
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.exceptions import TgLinkException


async def sendMessage(message, text, buttons=None, photo=None, **kwargs):
    try:
        if photo:
            if photo == 'IMAGES':
                photo = rchoice(config_dict['IMAGES'])

            # Attempt to send a photo message
            sent_message = await message.reply_photo(
                photo=photo,
                reply_to_message_id=message.message_id,
                caption=text,
                reply_markup=buttons,
                disable_notification=True,
                **kwargs
            )
        else:
            # Send a text message
            sent_message = await message.reply_text(
                text,
                reply_markup=buttons,
                disable_web_page_preview=True,
                disable_notification=True,
                **kwargs
            )

        return sent_message

    except FloodWait as f:
        LOGGER.warning(str(f))
        await sleep(f.value * 1.2)
        return await sendMessage(message, text, buttons, photo, **kwargs)

    except (PhotoInvalidDimensions, WebpageCurlFailed, MediaEmpty):
        # Handle cases where photo sending fails due to invalid dimensions or other issues
        if photo:
            des_dir = await download_image_url(photo)
            sent_message = await sendMessage(message, text, buttons, des_dir, **kwargs)
            await aioremove(des_dir)
            return sent_message

    except ReplyMarkupInvalid:
        # Handle invalid reply markup
        return await sendMessage(message, text, None, photo, **kwargs)

    except MessageEmpty:
        # Handle cases where the message content is empty
        return await sendMessage(message, text, parse_mode=ParseMode.DISABLED, **kwargs)

    except Exception as e:
        # Log any other unexpected errors
        LOGGER.error(format_exc())
        return str(e)


async def sendCustomMsg(chat_id, text, buttons=None, photo=None, debug=False):
    try:
        if photo:
            if photo == 'IMAGES':
                photo = rchoice(config_dict['IMAGES'])

            # Attempt to send a photo message
            sent_message = await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=buttons,
                disable_notification=True
            )
        else:
            # Send a text message
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=True,
                disable_notification=True,
                reply_markup=buttons
            )

        return sent_message

    except FloodWait as f:
        LOGGER.warning(str(f))
        await sleep(f.value * 1.2)
        return await sendCustomMsg(chat_id, text, buttons, photo, debug)

    except ReplyMarkupInvalid:
        # Handle invalid reply markup
        return await sendCustomMsg(chat_id, text, None, photo, debug)

    except Exception as e:
        # Log any other unexpected errors
        LOGGER.error(format_exc())
        return str(e)


async def chat_info(channel_id):
    channel_id = str(channel_id).strip()
    if channel_id.startswith('-100'):
        channel_id = int(channel_id)
    elif channel_id.startswith('@'):
        channel_id = channel_id.replace('@', '')
    else:
        return None
    try:
        return await bot.get_chat(channel_id)
    except (PeerIdInvalid, ChannelInvalid) as e:
        LOGGER.error(f"{e.NAME}: {e.MESSAGE} for {channel_id}")
        return None


async def sendMultiMessage(chat_ids, text, buttons=None, photo=None):
    msg_dict = {}
    for channel_id in chat_ids.split():
        channel_id, *topic_id = channel_id.split(':')
        topic_id = int(topic_id[0]) if len(topic_id) else None
        chat = await chat_info(channel_id)
        try:
            if photo:
                if photo == 'IMAGES':
                    photo = rchoice(config_dict['IMAGES'])

                # Attempt to send a photo message to multiple chats
                sent = await bot.send_photo(
                    chat_id=chat.id,
                    photo=photo,
                    caption=text,
                    reply_markup=buttons,
                    reply_to_message_id=topic_id,
                    disable_notification=True
                )
                msg_dict[f"{chat.id}:{topic_id}"] = sent

            else:
                # Send a text message to multiple chats
                sent = await bot.send_message(
                    chat_id=chat.id,
                    text=text,
                    disable_web_page_preview=True,
                    disable_notification=True,
                    reply_markup=buttons,
                    reply_to_message_id=topic_id
                )
                msg_dict[f"{chat.id}:{topic_id}"] = sent

        except FloodWait as f:
            LOGGER.warning(str(f))
            await sleep(f.value * 1.2)
            return await sendMultiMessage(chat_ids, text, buttons, photo)

        except Exception as e:
            LOGGER.error(str(e))

    return msg_dict


async def editMessage(message, text, buttons=None, photo=None):
    try:
        if message.media:
            if photo:
                photo = rchoice(config_dict['IMAGES']) if photo == 'IMAGES' else photo
                return await message.edit_media(InputMediaPhoto(photo, text), reply_markup=buttons)
            return await message.edit_caption(caption=text, reply_markup=buttons)

        await message.edit(text=text, disable_web_page_preview=True, reply_markup=buttons)

    except FloodWait as f:
        LOGGER.warning(str(f))
        await sleep(f.value * 1.2)
        return await editMessage(message, text, buttons, photo)

    except (MessageNotModified, MessageEmpty):
        pass

    except ReplyMarkupInvalid:
        return await editMessage(message, text, None, photo)

    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def editReplyMarkup(message, reply_markup):
    try:
        return await message.edit_reply_markup(reply_markup=reply_markup)

    except MessageNotModified:
        pass

    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def sendFile(message, file, caption=None, buttons=None):
    try:
        return await message.reply_document(
            document=file,
            quote=True,
            caption=caption,
            disable_notification=True,
            reply_markup=buttons
        )

    except FloodWait as f:
        LOGGER.warning(str(f))
        await sleep(f.value * 1.2)
        return await sendFile(message, file, caption, buttons)

    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def sendRss(text):
    try:
        # Determine whether to use the user or bot session to send the message
        if user:
            return await user.send_message(
                chat_id=config_dict['RSS_CHAT'],
                text=text,
                disable_web_page_preview=True,
                disable_notification=True
            )
        else:
            return await bot.send_message(
                chat_id=config_dict['RSS_CHAT'],
                text=text,
                disable_web_page_preview=True,
                disable_notification=True
            )

    except FloodWait as f:
        LOGGER.warning(str(f))
        await sleep(f.value * 1.2)
        return await sendRss(text)

    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def deleteMessage(message):
    try:
        await message.delete()

    except Exception as e:
        LOGGER.error(str(e))


async def auto_delete_message(cmd_message=None, bot_message=None):
    if config_dict['AUTO_DELETE_MESSAGE_DURATION'] != -1:
        await sleep(config_dict['AUTO_DELETE_MESSAGE_DURATION'])
        if cmd_message is not None:
            await deleteMessage(cmd_message)
        if bot_message is not None:
            await deleteMessage(bot_message)


async def delete_links(message):
    if config_dict['DELETE_LINKS']:
        if reply_to := message.reply_to_message:
            await deleteMessage(reply_to)
        await deleteMessage(message)
        

async def delete_all_messages():
    async with status_reply_dict_lock:
        for key, data in list(status_reply_dict.items()):
            try:
                del status_reply_dict[key]
                await deleteMessage(data[0])
            except Exception as e:
                LOGGER.error(str(e))


async def get_tg_link_content(link, user_id, decrypter=None):
    message = None
    user_sess = user_data.get(user_id, {}).get('usess', '')
    if link.startswith(('https://t.me/', 'https://telegram.me/', 'https://telegram.dog/', 'https://telegram.space/')):
        private = False
        msg = re_match(r"https:\/\/(t\.me|telegram\.me|telegram\.dog|telegram\.space)\/(?:c\/)?([^\/]+)(?:\/[^\/]+)?\/([0-9]+)", link)
    else:
        private = True
        msg = re_match(r"tg:\/\/(openmessage)\?user_id=([0-9]+)&message_id=([0-9]+)", link)
        if not (user or user_sess):
            raise TgLinkException('USER_SESSION_STRING or Private User Session required for this private link!')

    chat = msg.group(2)
    msg_id = int(msg.group(3))
    if chat.isdigit():
        chat = int(chat) if private else int(f'-100{chat}')

    if not private:
        try:
            message = await bot.get_messages(chat_id=chat, message_ids=msg_id)
            if message.empty:
                private = True
        except Exception as e:
            private = True
            if not (user or user_sess):
                raise e

    if private and user:
        try:
            user_message = await user.get_messages(chat_id=chat, message_ids=msg_id)
            if not user_message.empty:
                return user_message, 'user'
        except Exception as e:
            if not user_sess:
                raise TgLinkException(f"Bot User Session doesn't have access to this chat!. ERROR: {e}") from e

    if private and user_sess:
        if decrypter is None:
            return None, ""
        try:
            async with Client(user_id, session_string=decrypter.decrypt(user_sess).decode(), in_memory=True, no_updates=True) as usession:
                user_message = await usession.get_messages(chat_id=chat, message_ids=msg_id)
        except InvalidToken:
            raise TgLinkException("Provided Decryption Key is Invalid, Recheck & Retry")
        except Exception as e:
            raise TgLinkException(f"User Session doesn't have access to this chat!. ERROR: {e}") from e
        if not user_message.empty:
            return user_message, 'user_sess'
        else:
            raise TgLinkException("Privately Deleted or Not Accessible!")
    elif not private:
        return message, 'bot'
    else:
        raise TgLinkException("Bot can't download from GROUPS without joining! Set your Own Session to get access!")


async def update_all_messages(force=False):
    async with status_reply_dict_lock:
        if not status_reply_dict or not Interval or (not force and time() - list(status_reply_dict.values())[0][1] < 3):
            return
        for chat_id in list(status_reply_dict.keys()):
            status_reply_dict[chat_id][1] = time()
    async with download_dict_lock:
        msg, buttons = await sync_to_async(get_readable_message)
    if msg is None:
        return
    async with status_reply_dict_lock:
        for chat_id in list(status_reply_dict.keys()):
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id][0].text:
                rmsg = await editMessage(status_reply_dict[chat_id][0], msg, buttons, 'IMAGES')
                if isinstance(rmsg, str) and rmsg.startswith('Telegram says: [400'):
                    del status_reply_dict[chat_id]
                    continue
                status_reply_dict[chat_id][0].text = msg
                status_reply_dict[chat_id][1] = time()


async def sendStatusMessage(msg):
    async with download_dict_lock:
        progress, buttons = await sync_to_async(get_readable_message)
    if progress is None:
        return
    async with status_reply_dict_lock:
        chat_id = msg.chat.id
        if chat_id in list(status_reply_dict.keys()):
            message = status_reply_dict[chat_id][0]
            await deleteMessage(message)
            del status_reply_dict[chat_id]
        if message := await sendMessage(msg, progress, buttons, photo='IMAGES'):
            if hasattr(message, 'caption'):
                message.caption = progress
            else:
                message.text = progress
        status_reply_dict[chat_id] = [message, time()]
        if not Interval:
            Interval.append(setInterval(config_dict['STATUS_UPDATE_INTERVAL'], update_all_messages))


async def open_category_btns(message):
    user_id = message.from_user.id
    msg_id = message.message_id
    buttons = ButtonMaker()
    _tick = True
    if len(utds := await fetch_user_tds(user_id)) > 1:
        for _name in utds.keys():
            buttons.ibutton(f'{"✅️" if _tick else ""} {_name}', f"scat {user_id} {msg_id} {_name.replace
            .replace(' ', '_')}",
                )
                _tick = False
    else:
        for _name in categories_dict:
            buttons.ibutton(
                f'{"✅️" if _tick else ""} {_name}',
                f"scat {user_id} {msg_id} {_name.replace(' ', '_')}",
            )
            _tick = False
    await editMessage(
        message,
        f'Select a Category to download.{" Current User: " + (await user.get_me()).username if user else ""}',
        buttons.build(),
    )


async def send_search_message(update, ch_id, user_id, text=None):
    msg = await sendMessage(
        update,
        f'Searching {"in bot" if not text else text}{" for user" if not ch_id else " in chat"}  @{(await bot.get_me()).username}!..',
        disable_notification=True,
    )
    search_dict = await sync_to_async(fetch_user_dumps)(ch_id, user_id, text)
    if search_dict:
        text = f'Search Result for {search_dict["uinfo"]["fullname"]}: \n\n'
        text += "\n".join([f'{i+1}. {vid[0]} : {vid[1]}' for i, vid in enumerate(search_dict["video_list"])])
        text += "\n\nReply /dload [number] to Download!"
    else:
        text = f"No Search Result Found for {text if text else 'This User'}!"
    await editMessage(msg, text, photo='IMAGES')


async def send_help_message(update):
    await sendMessage(
        update,
        'Commands Available :\n\n'
        '/help : Show this message\n'
        '/start : To Start the Bot\n'
        '/stop : To Stop the Bot\n'
        '/sud : To Check my Sudo Users\n'
        '/ud : To Check my Users Dump\n'
        '/refresh : To Refresh Configurations\n\n'
        '/rmd : To Delete Telegram Messages\n'
        '/dlck : To Toggle Links Deletion\n'
        '/restart : To Restart the Bot\n'
        '/scat : To Search and Send Categories\n'
        '/sdump : To Search and Send User Dumps\n\n'
        '/info : To Get a Chat or Channel Info\n'
        '/msg : To Send a Custom Message\n'
        '/pm : To Send a PM to a User\n'
        '/dload : To Download a Video\n'
        '/search : To Search a User Dumps',
    )


async def send_pm(update, user_id):
    user, *text = update.text.split(' ', 1)
    if not text:
        await sendMessage(update, "Please provide a message to send!")
        return
    try:
        await user.send_message(
            int(user_id),
            f'{text[0]}\n\nMessage sent via @{(await bot.get_me()).username}!',
        )
        await sendMessage(update, 'Message Sent Successfully!')
    except Exception as e:
        await sendMessage(update, f'Error: {str(e)}')


async def process_msg(update):
    user_id = update.from_user.id
    if update.reply_to_message:
        await deleteMessage(update)
    if update.text.startswith('/'):
        if not config_dict['DEBUG_MODE'] and user_id not in config_dict['SUDO_USERS']:
            return
        if update.text == '/start':
            await sendMessage(update, f"Hi! I'm @{(await bot.get_me()).username}. How can I assist you?")
        elif update.text == '/help':
            await send_help_message(update)
        elif update.text == '/stop':
            await sendMessage(update, "Bot Stopped!")
            await bot.stop()
        elif update.text == '/sud':
            await sendMessage(update, f"My Sudo Users: {config_dict['SUDO_USERS']}")
        elif update.text == '/ud':
            await sendMessage(update, f"My User Dumps: {list(user_data.keys())}")
        elif update.text == '/refresh':
            await sendMessage(update, "Refreshing Configurations...")
            await bot.refresh_config()
            await sendMessage(update, "Configurations Refreshed!")
        elif update.text == '/rmd':
            config_dict['DELETE_LINKS'] = not config_dict['DELETE_LINKS']
            await sendMessage(update, f"Links Deletion {'Enabled' if config_dict['DELETE_LINKS'] else 'Disabled'}!")
        elif update.text == '/dlck':
            config_dict['DELETE_LINKS'] = not config_dict['DELETE_LINKS']
            await sendMessage(update, f"Links Deletion {'Enabled' if config_dict['DELETE_LINKS'] else 'Disabled'}!")
        elif update.text == '/restart':
            await sendMessage(update, "Bot Restarting...")
            await bot.restart()
        elif update.text.startswith('/scat'):
            cmd, *arg = update.text.split()
            if not arg:
                await open_category_btns(update)
            else:
                await send_search_message(update, None, int(arg[0]))
        elif update.text.startswith('/sdump'):
            cmd, *arg = update.text.split()
            if not arg:
                await open_category_btns(update)
            else:
                await send_search_message(update, int(arg[0]), int(arg[1]), 'User Dumps')
        elif update.text == '/info':
            await sendMessage(update, 'Use this command in reply to a message to get Chat Info!')
        elif update.text.startswith('/msg'):
            cmd, *arg = update.text.split(maxsplit=1)
            if not arg:
                await sendMessage(update, "Please provide a message to send!")
            else:
                await sendCustomMsg(int(arg[0]), arg[1])
        elif update.text.startswith('/pm'):
            await send_pm(update, user_id)
        elif update.text.startswith('/dload'):
            await send_help_message(update)
        elif update.text.startswith('/search'):
            cmd, *arg = update.text.split(maxsplit=1)
            if not arg:
                await sendMessage(update, "Please provide a username to search!")
            else:
                await send_search_message(update, None, arg[0])
    else:
        await sendMessage(update, "Invalid Command! Use /help to see available commands.")
