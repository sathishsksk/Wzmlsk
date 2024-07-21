import asyncio
from aiohttp import web
from time import time, monotonic
from datetime import datetime
from sys import executable
from os import execl as osexecl
from asyncio import create_subprocess_exec, gather, run as asyrun
from uuid import uuid4
from base64 import b64decode
from importlib import import_module, reload

from pytz import timezone
from bs4 import BeautifulSoup
from signal import signal, SIGINT
from aiofiles.os import path as aiopath, remove as aioremove
from aiofiles import open as aiopen
from pyrogram import idle
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, private, regex
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot, user, bot_name, config_dict, user_data, botStartTime, LOGGER, Interval, DATABASE_URL, QbInterval, INCOMPLETE_TASK_NOTIFIER, scheduler
from bot.version import get_version
from .helper.ext_utils.fs_utils import start_cleanup, clean_all, exit_clean_up
from .helper.ext_utils.bot_utils import get_readable_time, cmd_exec, sync_to_async, new_task, set_commands, update_user_ldata, get_stats
from .helper.ext_utils.db_handler import DbManger
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.message_utils import sendMessage, editMessage, editReplyMarkup, sendFile, deleteMessage, delete_all_messages
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.themes import BotTheme
from .modules import authorize, clone, gd_count, gd_delete, gd_list, cancel_mirror, mirror_leech, status, torrent_search, torrent_select, ytdlp, \
                     rss, shell, eval, users_settings, bot_settings, speedtest, save_msg, images, imdb, anilist, mediainfo, mydramalist, gen_pyro_sess, \
                     gd_clean, broadcast, category_select

async def health_check(request):
    return web.Response(text="OK", content_type="text/plain")

async def stats(client, message):
    msg, btns = await get_stats(message)
    await sendMessage(message, msg, btns, photo='IMAGES')

@new_task
async def start(client, message):
    buttons = ButtonMaker()
    buttons.ubutton(BotTheme('ST_BN1_NAME'), BotTheme('ST_BN1_URL'))
    buttons.ubutton(BotTheme('ST_BN2_NAME'), BotTheme('ST_BN2_URL'))
    reply_markup = buttons.build_menu(2)
    if len(message.command) > 1 and message.command[1] == "wzmlx":
        await deleteMessage(message)
    elif len(message.command) > 1 and config_dict['TOKEN_TIMEOUT']:
        userid = message.from_user.id
        encrypted_url = message.command[1]
        input_token, pre_uid = (b64decode(encrypted_url.encode()).decode()).split('&&')
        if int(pre_uid) != userid:
            return await sendMessage(message, BotTheme('OWN_TOKEN_GENERATE'))
        data = user_data.get(userid, {})
        if 'token' not in data or data['token'] != input_token:
            return await sendMessage(message, BotTheme('USED_TOKEN'))
        elif config_dict['LOGIN_PASS'] is not None and data['token'] == config_dict['LOGIN_PASS']:
            return await sendMessage(message, BotTheme('LOGGED_PASSWORD'))
        buttons.ibutton(BotTheme('ACTIVATE_BUTTON'), f'pass {input_token}', 'header')
        reply_markup = buttons.build_menu(2)
        msg = BotTheme('TOKEN_MSG', token=input_token, validity=get_readable_time(int(config_dict["TOKEN_TIMEOUT"])))
        return await sendMessage(message, msg, reply_markup)
    elif await CustomFilters.authorized(client, message):
        start_string = BotTheme('ST_MSG', help_command=f"/{BotCommands.HelpCommand}")
        await sendMessage(message, start_string, reply_markup, photo='IMAGES')
    elif config_dict['BOT_PM']:
        await sendMessage(message, BotTheme('ST_BOTPM'), reply_markup, photo='IMAGES')
    else:
        await sendMessage(message, BotTheme('ST_UNAUTH'), reply_markup, photo='IMAGES')
    await DbManger().update_pm_users(message.from_user.id)

async def token_callback(_, query):
    user_id = query.from_user.id
    input_token = query.data.split()[1]
    data = user_data.get(user_id, {})
    if 'token' not in data or data['token'] != input_token:
        return await query.answer('Already Used, Generate New One', show_alert=True)
    update_user_ldata(user_id, 'token', str(uuid4()))
    update_user_ldata(user_id, 'time', time())
    await query.answer('Activated Temporary Token!', show_alert=True)
    kb = query.message.reply_markup.inline_keyboard[1:]
    kb.insert(0, [InlineKeyboardButton(BotTheme('ACTIVATED'), callback_data='pass activated')])
    await editReplyMarkup(query.message, InlineKeyboardMarkup(kb))

async def login(_, message):
    if config_dict['LOGIN_PASS'] is None:
        return
    elif len(message.command) > 1:
        user_id = message.from_user.id
        input_pass = message.command[1]
        if user_data.get(user_id, {}).get('token', '') == config_dict['LOGIN_PASS']:
            return await sendMessage(message, BotTheme('LOGGED_IN'))
        if input_pass != config_dict['LOGIN_PASS']:
            return await sendMessage(message, BotTheme('INVALID_PASS'))
        update_user_ldata(user_id, 'token', config_dict['LOGIN_PASS'])
        return await sendMessage(message, BotTheme('PASS_LOGGED'))
    else:
        await sendMessage(message, BotTheme('LOGIN_USED'))

async def restart(client, message):
    restart_message = await sendMessage(message, BotTheme('RESTARTING'))
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await delete_all_messages()
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', 'gunicorn|aria2c|qbittorrent-nox|ffmpeg|rclone')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")

async def ping(_, message):
    start_time = monotonic()
    reply = await sendMessage(message, BotTheme('PING'))
    end_time = monotonic()
    ping_time_ms = int((end_time - start_time) * 1000)
    await editMessage(reply, BotTheme('PING_VALUE', value=ping_time_ms))
    
async def log_check():
    if config_dict['LEECH_LOG_ID']:
        for chat_id in config_dict['LEECH_LOG_ID'].split():
            chat_id, *topic_id = chat_id.split(":")
            try:
                try:
                    chat = await bot.get_chat(int(chat_id))
                except Exception:
                    LOGGER.error(f"Not Connected Chat ID : {chat_id}, Make sure the Bot is Added!")
                    continue
                if chat.type == ChatType.CHANNEL:
                    if not (await chat.get_member(bot.me.id)).privileges.can_post_messages:
                        LOGGER.error(f"Not Connected Chat ID : {chat_id}, Make the Bot is Admin in Channel to Connect!")
                        continue
                    if user and not (await chat.get_member(user.me.id)).privileges.can_post_messages:
                        LOGGER.error(f"Not Connected Chat ID : {chat_id}, Make the User is Admin in Channel to Connect!")
                        continue
                elif chat.type == ChatType.SUPERGROUP:
                    if not (await chat.get_member(bot.me.id)).status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                        LOGGER.error(f"Not Connected Chat ID : {chat_id}, Make the Bot is Admin in Group to Connect!")
                        continue
                    if user and not (await chat.get_member(user.me.id)).status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
                        LOGGER.error(f"Not Connected Chat ID : {chat_id}, Make the User is Admin in Group to Connect!")
                        continue
                LOGGER.info(f"Connected Chat ID : {chat_id}")
            except Exception as e:
                LOGGER.error(f"Not Connected Chat ID : {chat_id}, ERROR: {e}")

async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incomplete_task_message(cid, msg):
        try:
            if msg.startswith('Restarted Successfully!'):
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
                await bot.send_message(chat_id, msg, disable_web_page_preview=True, reply_to_message_id=msg_id)
                await aioremove(".restartmsg")
            else:
                await bot.send_message(chat_id=cid, text=msg, disable_web_page_preview=True,
                                       disable_notification=True)
        except Exception as e:
            LOGGER.error(e)
    if DATABASE_URL:
        if INCOMPLETE_TASK_NOTIFIER and (notifier_dict := await DbManager().get_incomplete_tasks()):
            for cid, data in notifier_dict.items():
                msg = 'Restarted Successfully!' if cid == chat_id else 'Bot Restarted!'
                for tag, links in data.items():
                    msg += f"\n\n👤 {tag} Do your tasks again. \n"
                    for index, link in enumerate(links, start=1):
                        msg += f" {index}: {link} \n"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg)
                            msg = ''
                if msg:
                    await send_incomplete_task_message(cid, msg)

        if STOP_DUPLICATE_TASKS:
            await DbManager().clear_download_links()


    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
        except:
            pass
        await aioremove(".restartmsg")

async def main():
    tasks = [
        start_cleanup(),
        torrent_search.initiate_search_tools(),
        restart_notification(),
        log_check(),  # No parameters are passed here
        set_commands(bot),
    ]
    await asyncio.gather(*tasks)

    bot.add_handler(MessageHandler(start, filters=command(BotCommands.StartCommand) & private))
    bot.add_handler(CallbackQueryHandler(token_callback, filters=regex(r'^pass')))
    bot.add_handler(MessageHandler(login, filters=command(BotCommands.LoginCommand) & private))
    bot.add_handler(MessageHandler(log, filters=command(BotCommands.LogCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(restart, filters=command(BotCommands.RestartCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(ping, filters=command(BotCommands.PingCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
    bot.add_handler(MessageHandler(bot_help, filters=command(BotCommands.HelpCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
    bot.add_handler(MessageHandler(stats, filters=command(BotCommands.StatsCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))

    LOGGER.info("Bot Started Successfully!")
    signal(SIGINT, exit_clean_up)

    app = web.Application()
    app.router.add_route('GET', '/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8888)  # Changed port to 8888
    await site.start()
  
    bot.loop.run_forever()

if __name__ == '__main__':
    bot.loop.run_until_complete(main())
