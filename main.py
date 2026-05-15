import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from apify import Actor


def normalize_channel_url(url: str) -> tuple[str, str]:
    raw = (url or "").strip()
    if raw.startswith("@"):
        channel = raw[1:]
        return f"https://t.me/s/{channel}", channel
    if not raw.startswith("http"):
        raw = f"https://t.me/{raw}"
    parsed = urlparse(raw)
    path_parts = [p for p in parsed.path.split("/") if p]
    if not path_parts:
        raise ValueError(f"Cannot parse Telegram channel URL: {url}")
    if path_parts[0] == "s" and len(path_parts) >= 2:
        channel = path_parts[1]
        return f"https://t.me/s/{channel}", channel
    channel = path_parts[0]
    return f"https://t.me/s/{channel}", channel


def parse_compact_number(value: str | None) -> int | None:
    if not value:
        return None
    text = value.strip().replace(" ", "").replace(",", ".")
    match = re.match(r"^([\d.]+)([KkMmКкМм]?)$", text)
    if not match:
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else None
    number = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix in ["k", "к"]:
        number *= 1_000
    elif suffix in ["m", "м"]:
        number *= 1_000_000
    return int(number)


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def extract_first_media_url(message: Any) -> str:
    photo = message.select_one(".tgme_widget_message_photo_wrap")
    if photo and photo.get("style"):
        style = photo.get("style", "")
        match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
        if match:
            return match.group(1)
    img = message.select_one("img")
    if img and img.get("src"):
        return img.get("src")
    video = message.select_one("video")
    if video and video.get("src"):
        return video.get("src")
    return ""


def parse_messages(html: str, channel: str, competitor: str, source_url: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    messages = soup.select(".tgme_widget_message")
    results: list[dict[str, Any]] = []
    for message in messages:
        text_el = message.select_one(".tgme_widget_message_text")
        post_text = clean_text(text_el.get_text("\n", strip=True) if text_el else "")
        time_el = message.select_one("time")
        date = time_el.get("datetime") if time_el else ""
        link_el = message.select_one(".tgme_widget_message_date a")
        post_url = link_el.get("href") if link_el else ""
        views_el = message.select_one(".tgme_widget_message_views")
        views = parse_compact_number(views_el.get_text(strip=True) if views_el else None)
        media_url = extract_first_media_url(message)
        if not post_text and not media_url:
            continue
        results.append({
            "date": date,
            "competitor": competitor or channel,
            "platform": "Telegram",
            "post_text": post_text,
            "image_url": media_url,
            "post_url": post_url,
            "likes": "",
            "comments": "",
            "shares": "",
            "views": views,
            "channel": channel,
            "source_url": source_url,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })
    return results


async def fetch_channel(client: httpx.AsyncClient, url: str, competitor: str, max_posts: int) -> list[dict[str, Any]]:
    public_url, channel = normalize_channel_url(url)
    Actor.log.info(f"Fetching Telegram channel: {public_url}")
    response = await client.get(public_url)
    response.raise_for_status()
    posts = parse_messages(response.text, channel, competitor, public_url)
    if max_posts > 0:
        posts = posts[-max_posts:]
    return posts


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}
        channels = actor_input.get("channels", [])
        max_posts = int(actor_input.get("maxPosts", 10))
        if not channels:
            raise ValueError("Input must include at least one Telegram channel in `channels`.")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
            for item in channels:
                if isinstance(item, str):
                    url = item
                    competitor = ""
                else:
                    url = item.get("url", "")
                    competitor = item.get("competitor", "")
                try:
                    posts = await fetch_channel(client, url, competitor, max_posts)
                    Actor.log.info(f"Collected {len(posts)} posts from {url}")
                    for post in posts:
                        await Actor.push_data(post)
                except Exception as exc:
                    Actor.log.exception(f"Failed to scrape {url}: {exc}")
                    await Actor.push_data({
                        "date": "",
                        "competitor": competitor,
                        "platform": "Telegram",
                        "post_text": "",
                        "image_url": "",
                        "post_url": "",
                        "likes": "",
                        "comments": "",
                        "shares": "",
                        "views": "",
                        "channel": "",
                        "source_url": url,
                        "error": str(exc),
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    })


if __name__ == "__main__":
    asyncio.run(main())
