# UCR Telegram Scraper

Custom Apify Actor for **UCR — Uchi Content Radar**.

It collects latest posts from public Telegram channels via the public `t.me/s/<channel>` web preview and outputs rows ready for Google Sheets / Make / OpenAI analysis.

## Input example

```json
{
  "channels": [
    { "competitor": "Фоксфорд", "url": "https://t.me/foxford" },
    { "competitor": "Skyeng", "url": "https://t.me/skyeng" }
  ],
  "maxPosts": 10
}
```

## Output fields

- `date`
- `competitor`
- `platform`
- `post_text`
- `image_url`
- `post_url`
- `likes`
- `comments`
- `shares`
- `views`
- `channel`
- `source_url`
- `collected_at`

## Limitations

This MVP works only with public Telegram channels available through `t.me/s/<channel>`.
Telegram public web preview does not reliably expose likes, comments, shares, polls, or all carousel media.
For the hackathon MVP this is enough to show automatic content collection and AI analysis.
