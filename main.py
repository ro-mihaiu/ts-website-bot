import os
import re
import json
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()

CHANNEL_SCHEMATIC = int(os.getenv("CHANNEL_SCHEMATIC", "0"))
CHANNEL_WORLD = int(os.getenv("CHANNEL_WORLD", "0"))
CHANNEL_VIDEO = int(os.getenv("CHANNEL_VIDEO", "0"))
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

DOWNLOAD_REGEX = re.compile(r"DN\s*:\s*(.+)")
LINK_REGEX = re.compile(r"Link\s*:\s*(https?://\S+)")
YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

farms = {}

def normalize_dn(dn: str) -> str:
    dn = dn.strip()
    dn = re.sub(r"<@!?\d+>", "", dn)
    dn = re.sub(r"<@&\d+>", "", dn)
    dn = dn.strip()
    return dn

def extract_dn_and_link(content: str):
    dn = None
    link = None
    dn_match = DOWNLOAD_REGEX.search(content)
    if dn_match:
        dn = normalize_dn(dn_match.group(1))
    link_match = LINK_REGEX.search(content)
    if link_match:
        link = link_match.group(1).rstrip(".")
    return dn, link

def extract_video_info(message: discord.Message):
    video_url = None
    video_title = None

    content = message.content or ""
    if message.embeds:
        for embed in message.embeds:
            if embed.type == "video" and embed.url:
                video_url = embed.url
                video_title = embed.title
                break
            if embed.type == "rich" and embed.url and ("youtube.com" in embed.url or "youtu.be" in embed.url):
                video_url = embed.url
                video_title = embed.title
                break
            if embed.description:
                content += "\n" + embed.description
            if embed.fields:
                for field in embed.fields:
                    content += f"\n{field.name}: {field.value}"

    if not video_url:
        yt_match = YOUTUBE_REGEX.search(content)
        if yt_match:
            video_id = yt_match.group(6)
            video_url = f"https://www.youtube.com/watch?v={video_id}"

    if not video_title:
        title_match = re.search(r"Title\s*:\s*(.+)", content)
        if title_match:
            video_title = title_match.group(1).strip()
        else:
            video_title = message.content.strip().split("\n")[0][:200] if message.content else "Untitled Video"

    return video_url, video_title, message.created_at.isoformat()


def add_farm_entry(dn, video_upload_date=None, video_link=None, world_link=None, schematic_link=None):
    if not dn:
        return
    farms.setdefault(dn, {"videos": [], "worlds": [], "schematics": []})
    if video_link and video_link not in farms[dn]["videos"]:
        farms[dn]["videos"].append({"date": video_upload_date, "link": video_link})
    if world_link and world_link not in farms[dn]["worlds"]:
        farms[dn]["worlds"].append(world_link)
    if schematic_link and schematic_link not in farms[dn]["schematics"]:
        farms[dn]["schematics"].append(schematic_link)


async def scan_channel(channel_id, processor):
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Channel {channel_id} not found")
        return
    print(f"Scanning channel: {channel.name} ({channel_id})")
    count = 0
    async for message in channel.history(limit=None):
        await processor(message)
        count += 1
        if count % 100 == 0:
            print(f"  Processed {count} messages...")
            await asyncio.sleep(0)
    print(f"  Finished {channel.name}: {count} messages")


async def process_download_message(message: discord.Message):
    content = message.content or ""
    if message.embeds:
        for embed in message.embeds:
            if embed.description:
                content += "\n" + embed.description
    dn, link = extract_dn_and_link(content)
    if dn and link:
        add_farm_entry(dn, schematic_link=link)


async def process_world_message(message: discord.Message):
    content = message.content or ""
    if message.embeds:
        for embed in message.embeds:
            if embed.description:
                content += "\n" + embed.description
    dn, link = extract_dn_and_link(content)
    if dn and link:
        add_farm_entry(dn, world_link=link)


async def process_video_message(message: discord.Message):
    video_url, video_title, video_date = extract_video_info(message)
    dn_match = DOWNLOAD_REGEX.search(message.content or "")
    dn = normalize_dn(dn_match.group(1)) if dn_match else video_title
    if video_url:
        add_farm_entry(dn, video_upload_date=video_date, video_link=video_url)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    if CHANNEL_SCHEMATIC:
        await scan_channel(CHANNEL_SCHEMATIC, process_download_message)
    if CHANNEL_WORLD:
        await scan_channel(CHANNEL_WORLD, process_world_message)
    if CHANNEL_VIDEO:
        await scan_channel(CHANNEL_VIDEO, process_video_message)

    output_path = "farms_builds.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for dn, data in farms.items():
            videos = data["videos"] or [{"date": None, "link": None}]
            worlds = data["worlds"] or [None]
            schematics = data["schematics"] or [None]

            for v in videos:
                for w in worlds:
                    for s in schematics:
                        record = {
                            "dn": dn,
                            "video_upload_date": v["date"],
                            "video_link": v["link"],
                            "world_link": w,
                            "schematic_link": s,
                        }
                        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nDone. Output written to {output_path}")
    print(f"Total unique DNs: {len(farms)}")
    await bot.close()


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not set in .env")
    bot.run(BOT_TOKEN)
