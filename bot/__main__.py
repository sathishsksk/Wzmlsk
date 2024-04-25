import asyncio
import aiofiles
import aiohttp
from aiohttp import web
from bs4 import BeautifulSoup
from datetime import datetime
import os
from requests import get as rget
from pytz import timezone
from signal import signal, SIGINT
from base64 import b64decode
from uuid import uuid4
from importlib import reload

# Assuming bot is properly imported from bot module
from bot import bot, config_dict, user_data, LOGGER, Interval, DATABASE_URL
from bot.version import get_version
from bot.helper.ext_utils.bot_utils import (
    get_readable_time,
    sync_to_async,
    update_user_ldata,
)
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.telegram_helper import (
    BotCommands,
    ButtonMaker,
    CustomFilters,
    BotTheme,
    sendMessage,
    editMessage,
    sendFile,
    delete_all_messages,
)
from bot.helper.listeners.aria2_listener import start_aria2_listener

async def stats(client, message):
    msg, btns = await get_stats(message)
    await sendMessage(message, msg, btns, photo='IMAGES')

async def start(client, message):
    buttons = ButtonMaker()
    buttons.ubutton(BotTheme('ST_BN1_NAME'), BotTheme('ST_BN1_URL'))
    buttons.ubutton(BotTheme('ST_BN2_NAME'), BotTheme('ST_BN2_URL'))
    reply_markup = buttons.build_menu(2)
    # Add your custom logic for handling start command based on message.command

async def token_callback(_, query):
    # Add your implementation for token callback logic

async def login(_, message):
    # Add your implementation for login logic

async def restart(client, message):
    # Add your implementation for restart logic

async def ping(_, message):
    # Add your implementation for ping logic

async def log(_, message):
    # Add your implementation for log logic

async def search_images():
    # Add your implementation for image search logic

async def bot_help(client, message):
    # Add your implementation for bot help logic

async def restart_notification():
    # Add your implementation for restart notification logic
    now = datetime.now(timezone(config_dict['TIMEZONE']))
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incomplete_task_message(cid, msg):
        try:
            if msg.startswith("⌬ <b><i>Restarted Successfully!</i></b>"):
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=msg, disable_web_page_preview=True)
                await aioremove(".restartmsg")
            else:
                await bot.send_message(chat_id=cid, text=msg, disable_web_page_preview=True, disable_notification=True)
        except Exception as e:
            LOGGER.error(e)

    if config_dict['INCOMPLETE_TASK_NOTIFIER'] and DATABASE_URL:
        if notifier_dict := await DbManager().get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = (
                    BotTheme('RESTART_SUCCESS', time=now.strftime('%I:%M:%S %p'), date=now.strftime('%d/%m/%y'), timz=config_dict['TIMEZONE'], version=get_version())
                    if cid == chat_id
                    else BotTheme('RESTARTED')
                )
                msg += "\n\n⌬ <b><i>Incomplete Tasks!</i></b>"
                for tag, links in data.items():
                    msg += f"\n➲ <b>User:</b> {tag}\n┖ <b>Tasks:</b>"
                    for index, link in enumerate(links, start=1):
                        msg_link, source = next(iter(link.items()))
                        msg += f" {index}. <a href='{source}'>S</a> ->  <a href='{msg_link}'>L</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incomplete_task_message(cid, msg)
                            msg = ''
                if msg:
                    await send_incomplete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=BotTheme('RESTART_SUCCESS', time=now.strftime('%I:%M:%S %p'), date=now.strftime('%d/%m/%y'), timz=config_dict['TIMEZONE'], version=get_version()))
        except Exception as e:
            LOGGER.error(e)
        await aioremove(".restartmsg")

async def log_check():
    # Add your implementation for log check logic

async def health_check(request):
    return web.Response(text="OK", content_type="text/plain")

async def main():
    tasks = [
        start_cleanup(),
        torrent_search.initiate_search_tools(),
        restart_notification(),
        search_images(),
        set_commands(bot),
        log_check(),
        start_aria2_listener(),
    ]
    await asyncio.gather(*tasks)

    # Add message handlers
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

    # Keep the event loop running indefinitely
    while True:
        try:
            await asyncio.sleep(60)  # Keep event loop alive with periodic sleep
        except KeyboardInterrupt:
            LOGGER.info("Bot Stopped by User.")
            break

if __name__ == "__main__":
    asyncio.run(main())
