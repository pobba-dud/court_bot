# court_bot — CourtReserve Booking Bot

A Python automation tool that books a tennis court on [CourtReserve](https://app.courtreserve.com) as soon as a desired slot opens, instead of refreshing by hand and losing it to someone faster.

## What it does

- Prompts once for your CourtReserve login, organization ID, and booking page URL, then saves them locally to `config.json` for future runs
- Takes a target date and time and validates that it's in the future
- Logs in automatically with Playwright, including the "Remember Me" flow
- Waits until the target booking moment, then finds the slot on the calendar
- Fills out the reservation form (reservation type, duration) and submits it
- Retries every ~5 seconds for up to ~2 minutes if the slot hasn't appeared yet

## Tech

- **Python** (asyncio)
- **Playwright** (async API, Chromium) for browser automation

## Setup

```bash
pip install playwright
playwright install chromium
```

## Run

```bash
python court_booker.py
```

On first run you'll be asked for your email, password (hidden input), organization ID, and booking URL. Then enter the date (`MM/DD/YYYY`) and time (`HH:MM AM/PM`) you want to reserve.

## Important — keep your config private

`config.json` stores your login locally so you don't have to re-enter it. **Never commit it.** It's already listed in `.gitignore` — if you fork this, keep it that way, and delete `config.json` any time you want to reset your saved login.

## Status / limitations

- Built for CourtReserve's current page layout; if CourtReserve changes its selectors, the booking flow will need updating.
- Reservation type and duration currently default to the first available option.
