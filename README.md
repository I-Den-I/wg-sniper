# wg-sniper

Real-time notifier for new room listings from WG-Gesucht and Kleinanzeigen,
pushed to Telegram.

The Munich-area WG market moves in minutes — landlords are flooded with
applicants within an hour of posting. `wg-sniper` shortens the loop between
"a matching room appears" and "you can react" from *whenever you next check
your email* to *seconds*, so you can send your intro message before the queue.

## How it works

Instead of scraping the sites (Cloudflare-protected, high ban risk), the bot
listens to the platforms' own saved-search email alerts:

```
WG-Gesucht / Kleinanzeigen saved searches
        │  (email alert)
        ▼
Gmail  ──IMAP IDLE──▶  wg-sniper  ──▶  per-source parser  ──▶  SQLite (dedup by ad id)
                                                                      │
                                                                      ▼
                                                    Telegram message (title · city · price · link)
                                                                      │
                                                         ad page fetched, message edited
                                                     (district · size · WG size · move-in date)
```

- **IMAP IDLE** keeps a persistent connection to Gmail — the server pushes new
  messages instantly, no polling. Each source is searched with
  `UNSEEN FROM "<sender>" SUBJECT "<hint>"`, so other mail from the same
  sender (landlord replies, account notices) is never fetched or marked read.
- **Parsers** turn each alert email into listings (ad id, title, city, and the
  price where the email carries it).
- **SQLite** in WAL mode with `INSERT OR IGNORE` on the ad id — one
  notification per listing. Listings whose Telegram send failed are retried on
  the next start.
- **Telegram** sends via aiogram v3. A fast first message goes out
  immediately; the ad page is then fetched and the same message is edited with
  the extra details.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
$EDITOR .env

python -m wg_sniper
```

Run the tests with `pip install pytest pytest-asyncio && pytest`.

## Setup

### 1. Gmail App Password

Regular Gmail passwords do not work for IMAP. Create an app-specific one:

1. Enable 2-Step Verification: <https://myaccount.google.com/security>
2. Generate an App Password: <https://myaccount.google.com/apppasswords>
3. Put the 16-character string into `IMAP_PASSWORD`.

Register on both platforms with this same Gmail address, so all alerts land in
the one inbox the bot watches.

### 2. Telegram bot

Create a bot via [@BotFather](https://t.me/BotFather), then send it any
message from your account. Fetch your chat id:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
```

Take `result[].message.chat.id` — put both the token and the id into `.env`.

### 3. Saved searches

**WG-Gesucht** — for each target city, under **Filter und Suchaufträge →
Angebote → Filter erstellen**:

- Type: `WG-Zimmer`
- `Neue Angebote per E-Mail`: enabled
- City, price ceiling, other preferences per taste

The free tier allows 10 filters.

**Kleinanzeigen** — search **Immobilien → Auf Zeit & WG** in a city with a
radius, set the filters, then press **Suche speichern** and keep
**Mitteilungen aktivieren** checked. Recommended filters: Art der Unterkunft
`Privatzimmer`, Mietart `unbefristet`, Angebotstyp `Angebote`, Anbieter
`Privat`, and a Warmmiete ceiling. One search with a large radius (e.g.
München +50 km) can replace many single-town WG-Gesucht filters.

## Deployment

The bot runs as a systemd service under a dedicated, unprivileged user. It
needs very little: ~100 MB RAM, no inbound ports (it only makes outbound
connections to Gmail, Telegram and the listing sites). The smallest VPS of any
provider is enough. These steps were used on Debian 12; Ubuntu 22.04+ works the
same way.

### Requirements

- A Linux server with systemd and Python 3.11+
- SSH access as root (or a user with sudo)
- The Gmail App Password, Telegram bot token and chat id from [Setup](#setup)

### 1. Install system packages

```bash
apt-get update
apt-get install -y python3 python3-venv python3-pip git ca-certificates
python3 --version   # must be 3.11 or newer
```

### 2. Create the service user and fetch the code

```bash
useradd --system --shell /usr/sbin/nologin wgsniper
git clone https://github.com/I-Den-I/wg-sniper.git /opt/wg-sniper
chown -R wgsniper:wgsniper /opt/wg-sniper
```

The service user has no login shell. Run everything inside `/opt/wg-sniper`
as that user with `sudo -u wgsniper ...`, so file ownership stays consistent.

### 3. Create the virtualenv and install

```bash
cd /opt/wg-sniper
sudo -u wgsniper python3 -m venv .venv
sudo -u wgsniper .venv/bin/pip install --no-cache-dir -e .
sudo -u wgsniper .venv/bin/python -c "import wg_sniper.__main__; print('OK')"
```

### 4. Configure

```bash
cp /opt/wg-sniper/.env.example /opt/wg-sniper/.env
nano /opt/wg-sniper/.env          # fill in IMAP_* and TELEGRAM_* values
chown wgsniper:wgsniper /opt/wg-sniper/.env
chmod 600 /opt/wg-sniper/.env     # secrets: readable by the service user only
```

To reuse a `.env` you already tested locally, copy it instead:
`scp .env root@<server>:/opt/wg-sniper/.env`, then run the `chown`/`chmod`
lines above.

### 5. Install and start the systemd service

```bash
cp /opt/wg-sniper/systemd/wg-sniper.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now wg-sniper
```

The unit (`systemd/wg-sniper.service`) runs `.venv/bin/python -m wg_sniper` as
`wgsniper`, restarts it 10 s after a crash, and sandboxes it
(`ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`,
`NoNewPrivileges=true`, writes allowed only to `/opt/wg-sniper`). If you
install to another path, edit `WorkingDirectory`, `EnvironmentFile`,
`ExecStart` and `ReadWritePaths` in the unit accordingly.

### 6. Verify

```bash
systemctl is-active wg-sniper            # -> active
journalctl -u wg-sniper -n 20 --no-pager
```

A healthy start logs `Start polling` (Telegram) and
`connected to imap.gmail.com as <your address>` (IMAP), and the bot posts
`WG-Sniper started (<commit>)` to your Telegram chat. Send `/status` to the
bot to see the last IMAP connect and the last processed email.

When the next alert arrives, the log shows
`processing N new message(s) from <sender>` followed by `new listing ...`.

### Updating

```bash
cd /opt/wg-sniper
sudo -u wgsniper git pull --ff-only
sudo -u wgsniper .venv/bin/pip install --no-cache-dir -e .
systemctl restart wg-sniper
journalctl -u wg-sniper -n 20 --no-pager
```

Database schema changes are applied automatically on start (idempotent
migrations); no manual step is needed.

### Uninstalling

```bash
systemctl disable --now wg-sniper
rm /etc/systemd/system/wg-sniper.service
systemctl daemon-reload
rm -rf /opt/wg-sniper
userdel wgsniper
```

Afterwards, revoke the Gmail App Password, delete or revoke the Telegram bot
token via @BotFather, and delete the saved searches on both platforms.

### Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| `AUTHENTICATIONFAILED` in the log | Wrong or revoked App Password, or 2-Step Verification off |
| `Missing required env var` on start | `.env` incomplete, or not readable by `wgsniper` |
| `IMAP search ... failed` | The IMAP server rejected the search; check `IMAP_FOLDER` |
| Alerts are in Gmail but nothing is sent | The alert was already read (only `UNSEEN` mail is processed), or a Gmail filter moved it out of `IMAP_FOLDER` |
| Telegram message has no price/size | The ad page could not be fetched or parsed; run with `WG_ENRICH_DUMP=1` to save the HTML to `./debug/` |
| Bot replies "This bot is private." | The message came from a chat other than `TELEGRAM_CHAT_ID` |

## Configuration

All settings via `.env` (loaded by `python-dotenv`); see `.env.example`.

| Variable            | Default             | Notes                                     |
| ------------------- | ------------------- | ----------------------------------------- |
| `IMAP_HOST`         | `imap.gmail.com`    | Any IMAP4 SSL server                      |
| `IMAP_PORT`         | `993`               |                                           |
| `IMAP_USER`         | *required*          |                                           |
| `IMAP_PASSWORD`     | *required*          | Gmail: App Password, 16 chars             |
| `IMAP_FOLDER`       | `INBOX`             |                                           |
| `TELEGRAM_BOT_TOKEN`| *required*          |                                           |
| `TELEGRAM_CHAT_ID`  | *required*          | Your personal chat id (integer)           |
| `DB_PATH`           | `./wg_sniper.db`    |                                           |
| `LOG_LEVEL`         | `INFO`              |                                           |

Debug flags (set inline for one-off runs):

- `WG_DEBUG_DUMP=1` — when a WG-Gesucht email yields zero listings, dump its
  HTML and href list into `./debug/` for offline inspection.
- `WG_ENRICH_DUMP=1` — when an ad page yields no price, dump its HTML into
  `./debug/`.

## Sources

Each source is an entry in `wg_sniper/sources.py`: sender domain, a subject
hint, an email parser and an ad-page parser.

| Source | Alert setup | Notes |
|--------|-------------|-------|
| WG-Gesucht | Filter und Suchaufträge, "Neue Angebote per E-Mail" | Email has titles only; price comes from the ad page |
| Kleinanzeigen | "Suche speichern" with Mitteilungen enabled | Email has title + price; ad ids are stored as `ka:<id>` |

To add a source, write a module with `parse_email(msg) -> list[Listing]` and
`parse_ad_page(html) -> Enrichment`, and register it in `SOURCES`.

## One-off maintenance scripts

### Re-enrich existing listings

If the enrichment logic changes (e.g. selector fixes), previously-sent
Telegram messages keep their old, possibly-wrong data. This re-fetches every
previously-notified ad page, updates the DB, and edits the already-sent
Telegram message in place (using the stored `tg_message_id`):

```bash
python -m wg_sniper.reenrich --dry-run  # log what would change, no writes
python -m wg_sniper.reenrich            # apply
```

On the server, run it from the app directory as the service user:
`cd /opt/wg-sniper && sudo -u wgsniper .venv/bin/python -m wg_sniper.reenrich --dry-run`.

Safe to re-run. Polite 2 s delay between ad-page fetches. Listings whose
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
| `/version` | Commit SHA + branch + startup time |

## Roadmap

- [x] Ad-page enrichment: fetch price/size/district/etc. from the listing page
      and `edit_message_text` the Telegram post
- [x] Telegram bot commands
- [x] Rate-limited send queue and crash notifications
- [x] Kleinanzeigen via saved-search email alerts
- [ ] ImmoScout24 via email alerts (same channel pattern)
- [ ] Cross-source deduplication (address + price fuzzy match)
- [ ] Direct WG-Gesucht poll for lower latency (Cloudflare-aware)
- [ ] Transit-time filter (commute to Munich city centre)
- [ ] Auto-reply with a saved message template (opt-in, rate-limited)

## License

Personal project — use at your own risk. Automating these platforms may
conflict with their terms of service; keep the deployment small and personal.
