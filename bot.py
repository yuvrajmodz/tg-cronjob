import asyncio
import logging
import uvloop
import json
import os
import aiohttp
from datetime import datetime, timedelta
from telethon import TelegramClient, events, functions, types, Button

api_id = 53965296 # Replace With Your Api id
api_hash = '67895668b623b2eb3fbwk490eb25b66' # Replace With Hash
bot_token = '765398443:Ar3oAs0H903W1VhFgRoj4zTj3UjY' # Replace With BotToken

logging.basicConfig(level=logging.INFO)

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

client = TelegramClient('httpcron_bot', api_id, api_hash).start(bot_token=bot_token)

user_states = {}

CRON_FILE = "crons.json"

if not os.path.exists(CRON_FILE):
    with open(CRON_FILE, "w") as f:
        json.dump([], f)


def load_crons():
    with open(CRON_FILE, "r") as f:
        return json.load(f)


def save_crons(crons):
    with open(CRON_FILE, "w") as f:
        json.dump(crons, f, indent=2)


async def make_request(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                await resp.text()
                return resp.status
    except Exception as e:
        logging.error(f"Request failed for {url}: {e}")
        return None


async def cron_scheduler():
    while True:
        crons = load_crons()
        now = datetime.utcnow()
        updated = False
        for cron in crons:
            last_time = datetime.fromisoformat(cron["last_requested_at"]) if cron["last_requested_at"] else None
            interval = int(cron["interval"])
            if not last_time or (now - last_time).total_seconds() >= interval:
                asyncio.create_task(make_request(cron["url"]))
                cron["last_requested_at"] = datetime.utcnow().isoformat()
                updated = True
        if updated:
            save_crons(crons)
        await asyncio.sleep(1)


@client.on(events.NewMessage(pattern='^/start$'))
async def start_handler(event):
    sender = await event.get_sender()
    first_name = getattr(sender, 'first_name', None) or 'Friend'
    welcome = (
        f"**Hey {first_name} 👋,**\n\n"
        "**Welcome To Our HttpCron Bot, Which Can Help You To Set CronJob in Any Url,**\n\n"
        "**We Provide Most Advance Cron Network, Support From 5 Second CronJob.**"
    )
    await event.reply(welcome, parse_mode='md')


@client.on(events.NewMessage(pattern='^/status$'))
async def status_handler(event):
    await event.reply("**Status: Running 🟢**", parse_mode='md')


@client.on(events.NewMessage(pattern='^/setcron$'))
async def setcron_handler(event):
    user_states[event.sender_id] = {"step": "waiting_url"}
    buttons = [
        [Button.inline("Cancel Process", data=f"cancel:{event.sender_id}")]
    ]
    await event.reply(
        "**Send me the URL on which you want to set the CronJob.**", 
        buttons=buttons,
        parse_mode='md'
    )
    

@client.on(events.NewMessage(pattern=r"^/manage$"))
async def manage_handler(event):
    await event.reply("**This Feature is coming soon...**")
    
   
@client.on(events.NewMessage(pattern=r"^/about$"))
async def manage_handler(event):
    await event.reply("**No Ads, No Charges, 24/7 Online.**\n\n**Manager: @Nactire**")
    
    
@client.on(events.NewMessage(pattern="/donate"))
async def donate(event):
    chat_id = event.chat_id
    url = f"https://api.telegram.org/bot{bot_token}/sendInvoice"

    data = {
        "chat_id": chat_id,
        "title": "DONATION",
        "description": "𝗜𝗡𝗩𝗢𝗜𝗖𝗘 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗘𝗗 🟢\n\n𝗧𝗛𝗔𝗡𝗞 𝗬𝗢𝗨 𝗙𝗢𝗥 𝗦𝗨𝗣𝗣𝗢𝗥𝗧𝗜𝗡𝗚 𝗨𝗦..\n\n𝗬𝗢𝗨𝗥 𝗗𝗢𝗡𝗔𝗧𝗜𝗢𝗡 𝗛𝗘𝗟𝗣𝗦 𝗨𝗦 𝗧𝗢 𝗜𝗠𝗣𝗥𝗢𝗩𝗘 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦, 𝗔𝗡𝗗 𝗣𝗥𝗢𝗩𝗜𝗗𝗘 𝗔 𝗕𝗘𝗧𝗧𝗘𝗥 𝗘𝗫𝗣𝗘𝗥𝗜𝗘𝗡𝗖𝗘 𝗙𝗢𝗥 𝗔𝗟𝗟 𝗨𝗦𝗘𝗥𝗦, 𝗘𝗩𝗘𝗥𝗬 𝗦𝗧𝗔𝗥 𝗖𝗢𝗨𝗡𝗧𝗦 𝗔𝗡𝗗 𝗜𝗧𝗦 𝗛𝗜𝗚𝗛𝗟𝗬 𝗔𝗣𝗣𝗥𝗘𝗖𝗜𝗔𝗧𝗘𝗗 💎",
        "payload": "donation_2_stars",
        "provider_token": "",
        "currency": "XTR",
        "prices": json.dumps([{"label": "Donate 2 Stars", "amount": 5}]),
        "start_parameter": "donation_2_stars", 
        "parse_mode": "Markdown"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as resp:
            result = await resp.json()

    if result.get("ok"):
        return
    else:
        await event.respond(f"Error generating invoice: {result.get('description')}")


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
            parse_mode='md'
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

        crons = load_crons()
        crons.append({
            "url": url,
            "interval": interval,
            "last_requested_at": datetime.utcnow().isoformat(),
            "chatid": event.sender_id
        })
        save_crons(crons)
        user_states.pop(event.sender_id, None)

        await event.edit(
            f"**Cron Setup Successfully 🟢**\n\n"
            f"**URL**: **{url}**\n\n"
            f"**Time Every: {interval} sec**\n\n"
            f"**First Response: {response_code}**",
            buttons=None,
            parse_mode='md'
        )


async def set_bot_commands():
    commands = [
        types.BotCommand(command="start", description="To Start Or Restart"),
        types.BotCommand(command="status", description="To Check Bot Status"),
        types.BotCommand(command="setcron", description="To Set CronJob On Url"),
        types.BotCommand(command="manage", description="To Manage CronJobs"),
        types.BotCommand(command="about", description="About Bot & Developer"),
        types.BotCommand(command="donate", description="To Donate Some Stars")
    ]
    await client(functions.bots.SetBotCommandsRequest(
        scope=types.BotCommandScopeDefault(),
        lang_code="en",
        commands=commands
    ))


if __name__ == '__main__':
    async def main():
        await set_bot_commands()
        asyncio.create_task(cron_scheduler())
        print('Bot is running with uvloop + Cron system...')
        await client.run_until_disconnected()

    with client:
        client.loop.run_until_complete(main())
