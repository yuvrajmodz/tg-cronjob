import asyncio
import logging
import uvloop
import json
import os
import aiohttp
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types, Button
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

api_id = 20265597
api_hash = '67895668b623b2eb3b45fd800eb25b66'
bot_token = '8344662520:AAEdHgggp4r4d1HH6zOmNXHB7VvmmmY2KCI'

logging.basicConfig(level=logging.INFO)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

client = TelegramClient('supercron', api_id, api_hash).start(bot_token=bot_token)

user_states = {}

CRON_FILE = "crons.json"

cache = {}
cache_lock = asyncio.Lock()

if not os.path.exists(CRON_FILE):
    with open(CRON_FILE, "w") as f:
        json.dump([], f)


def load_crons_from_file():
    with open(CRON_FILE, "r") as f:
        return json.load(f)


def save_crons_to_file(crons):
    with open(CRON_FILE, "w") as f:
        json.dump(crons, f, indent=2)


async def initialize_cache():
    async with cache_lock:
        crons = load_crons_from_file()
        cache.clear()
        for cron in crons:
            cache[cron["cron_id"]] = cron.copy()
        logging.info(f"Cache initialized with {len(cache)} cron jobs")


async def reload_cache_from_file():
    async with cache_lock:
        crons = load_crons_from_file()
        old_ids = set(cache.keys())
        new_ids = set(cron["cron_id"] for cron in crons)
        
        added = new_ids - old_ids
        deleted = old_ids - new_ids
        
        if added:
            logging.info(f"Cache: Detected {len(added)} new cron(s) - IDs: {added}")
        if deleted:
            logging.info(f"Cache: Detected {len(deleted)} deleted cron(s) - IDs: {deleted}")
        
        cache.clear()
        for cron in crons:
            cache[cron["cron_id"]] = cron.copy()
        
        logging.info(f"Cache reloaded: {len(cache)} total cron jobs")


async def update_cache_entry(cron_id, updates):
    async with cache_lock:
        if cron_id in cache:
            cache[cron_id].update(updates)


async def sync_cache_to_file():
    async with cache_lock:
        crons = list(cache.values())
        save_crons_to_file(crons)


class CronFileHandler(FileSystemEventHandler):
    
    def __init__(self, loop):
        self.loop = loop
        self.last_modified = 0
        
    def on_modified(self, event):
        if event.src_path.endswith(CRON_FILE):
            current_time = datetime.now().timestamp()
            if current_time - self.last_modified < 0.5:
                return
            self.last_modified = current_time
            
            logging.info(f"Watchdog: Detected change in {CRON_FILE}")
            asyncio.run_coroutine_threadsafe(reload_cache_from_file(), self.loop)


def start_watchdog(loop):
    event_handler = CronFileHandler(loop)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()
    logging.info("Watchdog started monitoring crons.json")
    return observer


async def make_request(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                await resp.text()
                return resp.status
    except Exception as e:
        logging.error(f"Request failed for {url}: {e}")
        return None


async def cron_scheduler():
    while True:
        now = datetime.utcnow()
        to_remove = []
        
        async with cache_lock:
            cron_ids = list(cache.keys())
        
        for cron_id in cron_ids:
            async with cache_lock:
                if cron_id not in cache:
                    continue
                cron = cache[cron_id].copy()
            
            last_time = datetime.fromisoformat(cron["last_requested_at"]) if cron["last_requested_at"] else None
            interval = int(cron["interval"])
            fail_count = cron.get("fail_count", 0)

            if not last_time or (now - last_time).total_seconds() >= interval:
                status = await make_request(cron["url"])

                if status is None:
                    fail_count += 1
                    await update_cache_entry(cron_id, {"fail_count": fail_count})
                    logging.warning(f"URL failed {fail_count} times: {cron['url']}")

                    if fail_count >= 4:
                        to_remove.append(cron_id)
                        try:
                            buttons = [
                                [Button.url("𝗢𝗣𝗘𝗡 𝗬𝗢𝗨𝗥 𝗨𝗥𝗟", url=cron["url"])]
                            ]
                            await client.send_message(
                                cron["chatid"],
                                f"**Cron Notice 🛑**\n\n"
                                f"**Since Last 4 Attempts Your CronJob URL not Responding.**\n\n"
                                f"**We Take it As an Invalid URL, We are Removed Your CronJob:**\n\n"
                                f"`{cron['url']}`",
                                buttons=buttons,
                                parse_mode='md'
                            )
                        except Exception as e:
                            logging.error(f"Failed to send message to {cron['chatid']}: {e}")
                else:
                    await update_cache_entry(cron_id, {
                        "fail_count": 0,
                        "last_requested_at": datetime.utcnow().isoformat()
                    })
        
        if to_remove:
            async with cache_lock:
                for cron_id in to_remove:
                    if cron_id in cache:
                        del cache[cron_id]
            await sync_cache_to_file()
            logging.info(f"Removed {len(to_remove)} failed cron(s) from cache and file")
        
        # Periodic sync to file (every 10 iterations)
        if random.randint(1, 10) == 1:
            await sync_cache_to_file()
        
        await asyncio.sleep(1)


@client.on(events.NewMessage(pattern='^/start$'))
async def start_handler(event):
    sender = await event.get_sender()
    first_name = getattr(sender, 'first_name', None) or 'Friend'
    welcome = (
        f"**Hey {first_name} 👋,**\n\n"
        "**Welcome To Our SuperCron Bot, Which Can Help You To Set CronJob in Any Url,**\n\n"
        "**We Provide Most Advance Cron Network, Support From 5 Second CronJob.**"
    )
    await event.reply(welcome, parse_mode='md')


@client.on(events.NewMessage(pattern='^/status$'))
async def status_handler(event):
    async with cache_lock:
        total_crons = len(cache)
    await event.reply(f"**Status: Running 🟢**\n\n**Active Crons: {total_crons}**", parse_mode='md')


@client.on(events.NewMessage(pattern='^/setcron$'))
async def setcron_handler(event):
    user_states[event.sender_id] = {"step": "waiting_url"}
    buttons = [
        [Button.inline("Cancel Process", data=f"cancel:{event.sender_id}")]
    ]
    await event.reply(
        "**Please Enter The URL**", 
        buttons=buttons,
        parse_mode='md'
    )


@client.on(events.NewMessage(pattern=r"^/manage$"))
async def manage_handler(event):
    async with cache_lock:
        user_crons = [cron for cron in cache.values() if cron["chatid"] == event.sender_id]
    
    if not user_crons:
        await event.reply("**You Don't Have Any Cron(s) To Manage 🛑**", parse_mode='md', link_preview=False)
        return
    
    message_parts = ["🌐 **𝗖𝗥𝗢𝗡 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧**:\n"]
    
    for cron in user_crons:
        message_parts.append(
            f"\n𝗨𝗥𝗟: **{cron['url']}**\n"
            f"𝗜𝗗: **{cron['cron_id']}**\n"
            f"𝗜𝗡𝗧𝗘𝗥𝗩𝗔𝗟: **{cron['interval']}**\n"
            f"𝗗𝗘𝗟𝗘𝗧𝗘: `/delete {cron['cron_id']}`\n\n"
        )
    
    await event.reply("".join(message_parts), parse_mode='md', link_preview=False)


@client.on(events.NewMessage(pattern=r"^/delete(?:\s+(\d+))?$"))
async def delete_handler(event):
    match = event.pattern_match
    cron_id_str = match.group(1)
    
    if not cron_id_str:
        await event.reply(
            "**Please Specify Cron ID To Delete 🛑**\n\n**Eg:** `/delete 676754`",
            parse_mode='md'
        )
        return
    
    cron_id = int(cron_id_str)
    
    async with cache_lock:
        target_cron = cache.get(cron_id)
    
    if not target_cron:
        await event.reply(
            "**The Provided Cron ID Doesn't Exist in Our Server, Please Check Be Carefully 🛑**",
            parse_mode='md'
        )
        return
    
    if target_cron["chatid"] != event.sender_id:
        await event.reply(
            "**The Provided Cron ID Doesn't Exist in Your Account, Please Check Be Carefully 🛑**",
            parse_mode='md'
        )
        return
    
    buttons = [
        [Button.inline("Sure", data=f"delete_confirm:{cron_id}")],
        [Button.inline("No, i'm Just Kidding", data=f"delete_cancel:{cron_id}")]
    ]
    
    await event.reply(
        "**Removing Confirmation ⚠️**\n\n"
        "**Are You Sure To Delete Targeted Cron?\n"
        "This Action Cannot Be Reversible 🛑**",
        buttons=buttons,
        parse_mode='md'
    )


@client.on(events.NewMessage)
async def url_receiver(event):
    state = user_states.get(event.sender_id)

    if not state or state.get("step") != "waiting_url":
        return

    if event.raw_text.strip().startswith("/setcron"):
        return

    url = event.raw_text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        buttons = [
            [Button.inline("Cancel Process", data=f"cancel:{event.sender_id}")]
        ]
        await event.reply(
            "**URL Format is invalid 🛑**\n\n"
            "**Please Send in Proper URL Format**\n\n"
            "**Example:** `https://example.com`",
            buttons=buttons,
            parse_mode='md',
            link_preview=False
        )
        return

    user_states[event.sender_id] = {"step": "waiting_time", "url": url}

    buttons = [
        [Button.inline("5 Sec", data=f"time:5:{event.sender_id}")], 
        [Button.inline("10 Sec", data=f"time:10:{event.sender_id}"),
         Button.inline("30 Sec", data=f"time:30:{event.sender_id}"),
         Button.inline("60 Sec", data=f"time:60:{event.sender_id}")],
        [Button.inline("1 Min", data=f"time:60:{event.sender_id}"),
         Button.inline("10 Min", data=f"time:600:{event.sender_id}"),
         Button.inline("60 Min", data=f"time:3600:{event.sender_id}")],
        [Button.inline("6 Hour", data=f"time:21600:{event.sender_id}"),
         Button.inline("12 Hour", data=f"time:43200:{event.sender_id}"),
         Button.inline("24 Hour", data=f"time:86400:{event.sender_id}")],
        [Button.inline("Cancel Process", data=f"cancel:{event.sender_id}")]
    ]

    await event.reply(
        f"**URL: {url}**\n\n"
        "**Please Choose how often the CronJob URL should be requested — every few seconds or minutes.**",
        buttons=buttons,
        parse_mode='md'
    )


@client.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode()
    
    if data.startswith("cancel"):
        _, uid = data.split(":")
        if str(event.sender_id) == uid:
            user_states.pop(event.sender_id, None)
            await event.edit("**Process Cancelled 🛑**", buttons=None, parse_mode='md')
    
    elif data.startswith("time"):
        _, seconds, uid = data.split(":")
        if str(event.sender_id) != uid:
            return
        state = user_states.get(event.sender_id)
        if not state or state.get("step") != "waiting_time":
            return
        url = state["url"]
        interval = int(seconds)

        response_code = await make_request(url)

        if response_code is None:
            user_states.pop(event.sender_id, None)
            await event.edit(
                "**Cron Setup Failed 🛑**\n\n"
                "**The Provided URL is Not a Valid URL, Please Recheck Your URL And Then Request Again To Set CronJob.**",
                buttons=None,
                parse_mode='md'
            )
            return

        cron_id = random.randint(1000000, 9999999)
        
        new_cron = {
            "url": url,
            "cron_id": cron_id,
            "interval": interval,
            "last_requested_at": datetime.utcnow().isoformat(),
            "chatid": event.sender_id,
            "fail_count": 0
        }
        
        async with cache_lock:
            cache[cron_id] = new_cron.copy()
        
        crons = load_crons_from_file()
        crons.append(new_cron)
        save_crons_to_file(crons)
        
        user_states.pop(event.sender_id, None)

        await event.edit(
            f"**Cron Setup Successfully 🟢**\n\n"
            f"**URL**: **{url}**\n\n"
            f"**Time Every: {interval} sec**\n\n"
            f"**First Response: {response_code}**",
            buttons=None,
            parse_mode='md',
            link_preview=False
        )
    
    elif data.startswith("delete_confirm"):
        _, cron_id_str = data.split(":")
        cron_id = int(cron_id_str)

        async with cache_lock:
            target_cron = cache.get(cron_id)
        
        if not target_cron or target_cron["chatid"] != event.sender_id:
            await event.edit(
                "**Access Denied 🛑**",
                buttons=None,
                parse_mode='md'
            )
            return
        
        async with cache_lock:
            if cron_id in cache:
                del cache[cron_id]
        
        crons = load_crons_from_file()
        crons = [c for c in crons if c["cron_id"] != cron_id]
        save_crons_to_file(crons)
        
        await event.edit(
            f"**Cron Removed Successfully 🟢**\n\n"
            f"**URL:** {target_cron['url']}\n"
            f"**CRON ID**: **{target_cron['cron_id']}**",
            buttons=None,
            parse_mode='md',
            link_preview=False
        )
    
    elif data.startswith("delete_cancel"):
        await event.edit(
            "**Action Cancelled Successfully 🟢**\n\n"
            "**Please Don't Kidding Me Again.**",
            buttons=None,
            parse_mode='md',
        )


@client.on(events.NewMessage(pattern=r"^/about$"))
async def about_handler(event):
    await event.reply("**No Ads, No Charges, 24/7 Online.**\n\n**Manager: @Nactire**")


async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="To Start Or Restart"),
        types.BotCommand(command="status", description="To Check Bot Status"),
        types.BotCommand(command="setcron", description="To Set CronJob On Url"),
        types.BotCommand(command="manage", description="To Manage CronJobs"),
        types.BotCommand(command="about", description="About Bot & Developer")
    ]
    await client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code="en",
        commands=commands
    ))


if __name__ == '__main__':
    async def main():
        await initialize_cache()
        
        await set_bot_commands()
        
        loop = asyncio.get_event_loop()
        observer = start_watchdog(loop)
        
        asyncio.create_task(cron_scheduler())
        
        print('Bot is Running...')
        
        try:
            await client.run_until_disconnected()
        finally:
            observer.stop()
            observer.join()

    with client:
        client.loop.run_until_complete(main())