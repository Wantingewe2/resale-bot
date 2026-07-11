# Resale Listing Monitor

Polls eBay, Mercari, Depop, and Vinted for new listings matching your saved
searches, and alerts you on Discord/Telegram the moment something new shows
up. Dedupes locally so you're never pinged twice for the same item.

## Before you start: platform reliability is not equal

| Platform | Method | Reliability |
|---|---|---|
| eBay | Official Browse API (OAuth) | High - this is a real, supported API |
| Depop | Unofficial JSON search endpoint | Medium - works well, can change without notice |
| Vinted | Unofficial JSON catalog endpoint | Medium - has bot detection (Datadome), may need a cookie |
| Mercari | Scraped from rendered search page | Low - their real API needs signed tokens we can't replicate; this adapter parses embedded page JSON instead, which is the most likely of the four to break |

None of Mercari, Depop, or Vinted publish a developer API, so those three
adapters call the same internal endpoints their own websites use. That's
standard practice for personal-use tools like this, but it also means:
using this against their Terms of Service is your call to make, and you
should expect occasional breakage and should keep request volume low
(the defaults in `config.yaml` are deliberately conservative - don't drop
`poll_interval_seconds` below ~300 or you risk IP blocks).

## Setup

1. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Get eBay API credentials** (free)
   - Sign up at https://developer.ebay.com
   - Create a keyset, use the **Production** Client ID/Secret
   - Put them in `.env` (copy `.env.example` first)

3. **Set up a notification channel**
   - **Discord**: Server Settings → Integrations → Webhooks → New Webhook → copy the URL into `DISCORD_WEBHOOK_URL`
   - **Telegram**: message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`. Message your new bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to find your `chat_id`.
   - Toggle which one(s) are active in `config.yaml` under `notifications:`

4. **Define what you're hunting for** in `config.yaml`:
   ```yaml
   searches:
     - name: "Vintage Carhartt Jacket"
       query: "vintage carhartt jacket"
       min_price: 10
       max_price: 80
       platforms: [ebay, mercari, depop, vinted]
   ```

5. **Run it**
   ```bash
   python main.py
   ```
   It runs forever, polling every `poll_interval_seconds` (default 300s / 5 min).

## Running as a persistent service

**Option A - systemd (Linux server/VPS):**
```ini
# /etc/systemd/system/resale-bot.service
[Unit]
Description=Resale Listing Monitor
After=network.target

[Service]
WorkingDirectory=/opt/resale-bot
ExecStart=/opt/resale-bot/venv/bin/python main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now resale-bot
```

**Option B - Docker:**
```bash
docker build -t resale-bot .
docker run -d --name resale-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  resale-bot
```
(Update `database_path` and `logging.file` in `config.yaml` to `data/...` first so they persist in the volume.)

## Troubleshooting

- **"No platforms initialized"** → check `.env` has eBay credentials if `ebay` is in any search's `platforms:` list.
- **Mercari returns nothing** → their page structure changed; see the comment at the top of `bot/platforms/mercari.py` for what to check.
- **Vinted 401/403s** → grab a session cookie from your browser (DevTools → Application → Cookies on vinted.com) and set `VINTED_COOKIE` in `.env`.
- **Getting rate-limited** → raise `poll_interval_seconds` and `inter_platform_delay_seconds` in `config.yaml`.

## Project layout
```
resale-bot/
├── main.py                 # entry point
├── config.yaml              # your searches, filters, intervals
├── .env                      # secrets (not committed)
├── bot/
│   ├── config.py            # loads config.yaml + .env
│   ├── db.py                # SQLite dedupe store
│   ├── notifier.py          # Discord/Telegram senders
│   ├── scheduler.py         # the main polling loop
│   └── platforms/
│       ├── base.py          # shared Listing model + Platform interface
│       ├── ebay.py
│       ├── mercari.py
│       ├── depop.py
│       └── vinted.py
```

Adding a new search costs nothing (just another entry in `config.yaml`).
Adding a new platform means implementing `Platform.search()` in a new file
and registering it in `bot/platforms/__init__.py`.
