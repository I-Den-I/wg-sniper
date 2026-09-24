# wg-sniper

Real-time notifier for new WG-Gesucht room listings, pushed to Telegram.

The Munich-area WG market moves in minutes — landlords are flooded with
applicants within an hour of posting. `wg-sniper` shortens the loop between
"a matching room appears" and "you can react" from *whenever you next check
your email* to *seconds*, so you can send your intro message before the queue.

## How it works

Instead of scraping the site (Cloudflare-protected, high ban risk), the bot
listens to WG-Gesucht's own official email alerts:

```
WG-Gesucht saved searches
        │  (sofort E-Mail)
        ▼
Gmail  ──IMAP IDLE──▶  wg-sniper  ──▶  BS4 parser  ──▶  SQLite (dedup by ad_id)
                                                                │
                                                                ▼
                                                         Telegram bot
                                                         (title · city · link)
```

- **IMAP IDLE** keeps a persistent connection to Gmail — the server pushes new
  messages instantly, no polling.
- **Parser** decodes MIME-encoded subjects, unwraps tracking URLs, extracts
  ad IDs and titles by document-order pairing (avoids the "closing quote of A
  paired with opening quote of B" trap that a naive regex has).
- **SQLite** in WAL mode with `INSERT OR IGNORE` on `ad_id` — one notification
  per listing, safe under concurrent writes when multiple sources are added
  later.
- **Telegram** sends via aiogram v3; Telegram's own link preview enriches each
  message with a photo and description from the ad page.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
$EDITOR .env

python -m wg_sniper
```

## Setup

### 1. Gmail App Password

Regular Gmail passwords stopped working for IMAP in 2022. Create an app-specific
one:

1. Enable 2-Step Verification: <https://myaccount.google.com/security>
2. Generate an App Password: <https://myaccount.google.com/apppasswords>
3. Put the 16-character string into `IMAP_PASSWORD`.

Consider a dedicated Gmail account so a busy inbox doesn't dilute the search
scope (IMAP `SEARCH FROM "wg-gesucht.de"` filters server-side, but a clean
mailbox is one less thing to worry about).

### 2. Telegram bot

Create a bot via [@BotFather](https://t.me/BotFather), then send it any
message from your account. Fetch your chat id:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
```

Take `result[].message.chat.id` — put both the token and the id into `.env`.

### 3. WG-Gesucht saved searches

For each target city, create a saved search on wg-gesucht.de under **Filter
und Suchaufträge → Angebote → Filter erstellen** with:

- Type: `WG-Zimmer`
- `Neue Angebote per E-Mail`: enabled (sofort)
- City, price ceiling, other preferences per taste

Free tier caps at 10 filters; premium raises the ceiling.

## Deploy on a VPS (systemd)

```bash
sudo useradd -r -s /usr/sbin/nologin wgsniper
sudo mkdir -p /opt/wg-sniper
sudo chown wgsniper:wgsniper /opt/wg-sniper

# rsync the project into /opt/wg-sniper, create .venv, install deps,
# drop your .env at /opt/wg-sniper/.env

sudo cp systemd/wg-sniper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wg-sniper
journalctl -u wg-sniper -f
```

The unit sets `Restart=on-failure` with a 10-second backoff, so transient
network hiccups self-heal without intervention.

## Configuration

All settings via `.env` (loaded by `python-dotenv`); see `.env.example`.

| Variable            | Default             | Notes                                     |
| ------------------- | ------------------- | ----------------------------------------- |
| `IMAP_HOST`         | `imap.gmail.com`    | Any IMAP4 SSL server                      |
| `IMAP_PORT`         | `993`               |                                           |
| `IMAP_USER`         | *required*          |                                           |
| `IMAP_PASSWORD`     | *required*          | Gmail: App Password, 16 chars             |
| `IMAP_FOLDER`       | `INBOX`             | Use a label if filtering server-side      |
| `TELEGRAM_BOT_TOKEN`| *required*          |                                           |
| `TELEGRAM_CHAT_ID`  | *required*          | Your personal chat id (integer)           |
| `DB_PATH`           | `./wg_sniper.db`    |                                           |
| `LOG_LEVEL`         | `INFO`              |                                           |
| `WG_SENDER_FILTER`  | `wg-gesucht.de`     | Substring; applied at IMAP SEARCH level   |

Debug flag (set inline for one-off runs):

- `WG_DEBUG_DUMP=1` — when a WG-Gesucht email yields zero listings, dump its
  HTML and href list into `./debug/` for offline inspection.

## One-off maintenance scripts

### Re-enrich existing listings

If the enrichment logic changes (e.g. selector fixes), previously-sent
Telegram messages keep their old, possibly-wrong data. This re-fetches every
previously-notified ad page, updates the DB, and edits the already-sent
Telegram message in place (using the stored `tg_message_id`):

```bash
python -m wg_sniper.reenrich            # applies changes
python -m wg_sniper.reenrich --dry-run  # log what would change, no writes
```

Safe to re-run. Polite 2s delay between ad-page fetches. Listings whose
Telegram message can no longer be edited (e.g. deleted by the user) are
logged and skipped, not treated as fatal.

## Bot commands

Send these to the bot in Telegram (all restricted to the `TELEGRAM_CHAT_ID` in
`.env`; anyone else who finds the bot's username gets a polite refusal).

| Command | What it does |
|---------|--------------|
| `/start`, `/help` | Greeting and command list |
| `/ping` | Liveness check + process uptime |
| `/status` | Last IMAP connect / last email processed / last crash |
| `/stats` | Total, today, last 7 days, top cities |
| `/recent [N]` | Re-send last N notified listings (default 5, max 20) |
| `/mem`, `/cpu` | Server memory and CPU load |
| `/pause`, `/resume` | Silence notifications without stopping the service |
| `/lang` | Toggle interface between Ukrainian and English |
| `/version` | Commit SHA + branch + startup time |

## Roadmap

- [x] Ad-page enrichment (v2): fetch price/size/district/etc. from the listing
      page and `edit_message_text` the Telegram post
- [x] Telegram bot commands with i18n (UA/EN) (v2)
- [x] Rate-limited send queue and crash notifications (v2)
- [ ] Kleinanzeigen via RSS (no login, no anti-bot)
- [ ] ImmoScout24 via email alerts (same channel pattern)
- [ ] Cross-source deduplication (address + price fuzzy match)
- [ ] Direct WG-Gesucht poll for lower latency (Cloudflare-aware, Camoufox)
- [ ] MVV/DB transit-time filter (Munich Marienplatz commute target)
- [ ] Auto-reply with a saved `Vorlage` (opt-in, rate-limited, humanized)

## License

Personal project — use at your own risk. Scraping/automation may conflict with
platform ToS; keep the deployment small and personal.
