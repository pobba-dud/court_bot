import asyncio
import json
import os
from datetime import datetime
from getpass import getpass

from playwright.async_api import async_playwright

CONFIG_FILE = "config.json"
DEV_MODE = True  # Set False for production


def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
        print("✅ Settings loaded from config.json.")
        print("   If you'd like to update your login or booking info, please delete 'config.json' and restart the program.\n")
        return data
    return None


def prompt_user_settings():
    print("It looks like you're not logged in yet.")
    print("Once saved, to change login info just delete config.json.\n")
    email = input("Enter your email: ")
    password = getpass("Enter your password (input hidden): ")
    org_id = input("Enter your organization ID (e.g. 5915): ")
    booking_url = input("Enter the booking URL (full URL where bookings are made): ")
    return {
        "email": email,
        "password": password,
        "org_id": org_id,
        "booking_url": booking_url,
    }


def prompt_booking_datetime():
    while True:
        date_str = input("Enter the date to reserve (MM/DD/YYYY): ")
        time_str = input("Enter the time to reserve (HH:MM AM/PM): ")
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M %p")
            if dt <= datetime.now():
                print("❌ The date and time must be in the future. Please try again.\n")
                continue
            return dt
        except ValueError:
            print("❌ Invalid date/time format. Please try again.\n")


async def login(page, config):
    login_url = f"https://app.courtreserve.com/Online/Account/LogIn/{config['org_id']}"
    await page.goto(login_url)
    print("[dev] Navigated to login page")

    # Check if login required
    if await page.query_selector('input[name="email"]'):
        print("🔐 Not logged in — submitting login form...")
        await page.fill('input[name="email"]', config['email'])
        await page.fill('input[name="password"]', config['password'])

        remember_me_label = await page.query_selector('span.ant-checkbox-label:text("Remember Me")')
        if remember_me_label:
            parent = await remember_me_label.evaluate_handle('node => node.parentElement')
            if parent:
                await parent.click()
                print("☑️ Clicked 'Remember Me' checkbox")

        # Click Continue button and wait for navigation
        await page.get_by_test_id("Continue").click()
        try:
            await page.wait_for_navigation(timeout=10000)
            print("✅ Navigation after login succeeded")
        except Exception:
            print("⚠️ Navigation did not happen after login")
    else:
        print("✅ Already logged in")

    # Confirm login success by waiting for "Hours of Availability"
    try:
        await page.wait_for_selector('div.candidate_widget.home5 >> text="Hours of Availability"', timeout=10000)
        print("✅ Logged in successfully.")
        return True
    except Exception:
        print("❌ Login failed: 'Hours of Availability' not found")
        return False


async def wait_until(target_dt):
    now = datetime.now()
    seconds = (target_dt - now).total_seconds()
    print(f"[dev] Waiting {int(seconds)} seconds until booking time {target_dt.strftime('%m/%d/%Y %I:%M %p')}")

    while seconds > 0:
        print(f"⏳ {int(seconds)} seconds remaining...")
        await asyncio.sleep(min(seconds, 5))
        seconds -= min(seconds, 5)


import os  # for os.name

async def attempt_booking(page, booking_dt):
    date_str = booking_dt.strftime("%m/%d/%Y")
    try:
        full_date_str = booking_dt.strftime("%A, %B %-d, %Y")
    except ValueError:
        full_date_str = booking_dt.strftime("%A, %B %#d, %Y")

    try:
        time_str = booking_dt.strftime("%-I:%M %p")
    except ValueError:
        time_str = booking_dt.strftime("%#I:%M %p")

    print(f"[dev] Looking for slot on {date_str} at {time_str}")
    # Open the calendar popup by clicking the calendar toggle button
    calendar_toggle = await page.query_selector('a.k-nav-current')
    if not calendar_toggle:
        print("❌ Calendar toggle button not found.")
        return False
    await calendar_toggle.click()
    await page.wait_for_timeout(1000)  # Wait for calendar to open

    # Select the date by matching the full date text in the calendar popup
    date_link = await page.query_selector(f'a.k-link[title="{full_date_str}"]')
    if not date_link:
        print(f"❌ Date {full_date_str} not found in calendar popup.")
        return False

    await date_link.click()
    await page.wait_for_timeout(1500)  # Wait for times to load

    # Search for the time slot button (exact match)
    slot_button = await page.query_selector(f'button:has-text("{time_str}")')
    if not slot_button:
        print(f"🔄 Slot for {time_str} not available yet. Retrying shortly...")
        return False

    await slot_button.click()
    print(f"✔️ Selected slot for {time_str}")

    # Wait for modal to appear
    await page.wait_for_selector('div.modal-header-container', timeout=5000)

    # --- Fill modal form ---

    # Select first option in Reservation Type dropdown
    # The dropdown is Kendo UI widget, input hidden, but visible dropdown is a span/button combo
    # get element handle first
    reservation_type_input = await page.query_selector('#ReservationTypeId')
    if not reservation_type_input:
        print("❌ ReservationTypeId input not found in modal.")
        return False

    dropdown_button = await reservation_type_input.evaluate_handle(
    "(el) => el.parentElement.querySelector('button.k-select')"
    )
    if dropdown_button:
        await dropdown_button.click()
        # wait for dropdown list to appear - the id might be dynamic or placed in a popup container
        try:
            await page.wait_for_selector('ul.k-list-container ul li.k-item', timeout=3000)
        except Exception:
            print("❌ Dropdown options did not appear in time.")
            return False

        options = await page.query_selector_all('ul.k-list-container ul li.k-item')
        print(f"[dev] Found {len(options)} reservation type options.")
        if options:
            # click the first option (e.g. "Singles")
            await options[0].click()
        else:
            print("❌ No reservation type options found after waiting.")
            return False
    else:
        # fallback if no dropdown button
        await page.select_option('#ReservationTypeId', '1')



    # Set duration dropdown to "1 hour" or first option if possible
    duration_dropdown = await page.query_selector('#Duration')
    if duration_dropdown:
        await duration_dropdown.click()
        await page.wait_for_timeout(500)
        first_duration_option = await page.query_selector('ul#Duration_listbox li.k-item')
        if first_duration_option:
            await first_duration_option.click()
        else:
            print("⚠️ Duration dropdown options not found; skipping duration selection.")
    else:
        print("⚠️ Duration dropdown not found; skipping duration selection.")

    # Submit the modal form by clicking Save button
    save_button = await page.query_selector('button[data-testid="save-btn"]')
    if not save_button:
        print("❌ Save button not found in modal.")
        return False

    await save_button.click()
    print("📤 Submitted booking form.")

    # Optional: wait for confirmation or modal to close
    try:
        await page.wait_for_selector('div.modal-header-container', state='detached', timeout=5000)
        print("🎉 Booking modal closed — booking likely successful!")
    except Exception:
        print("⚠️ Modal did not close immediately; booking status uncertain.")

    return True

async def main():
    config = load_config()
    if not config:
        config = prompt_user_settings()
        save_config(config)

    booking_dt = prompt_booking_datetime()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not DEV_MODE)
        page = await browser.new_page()

        logged_in = await login(page, config)
        if not logged_in:
            print("❌ Login failed. Exiting.")
            await browser.close()
            return

        # Navigate explicitly to the booking page
        print(f"[dev] Navigating to booking page: {config['booking_url']}")
        await page.goto(config['booking_url'])
        await page.wait_for_timeout(3000)  # wait for slots to load

        if DEV_MODE:
            print("🛠 DEV MODE active — simulating short wait...")
            await wait_until(datetime.now() + timedelta(seconds=6))
        else:
            await wait_until(booking_dt)

        # Try booking loop: retry every ~5 seconds until successful or timeout (max 2 mins)
        max_retries = 24
        retries = 0
        success = False
        while retries < max_retries and not success:
            success = await attempt_booking(page, booking_dt)
            if not success:
                retries += 1
                await asyncio.sleep(5)

        if not success:
            print("⚠️ Failed to book the slot after multiple attempts.")

        if DEV_MODE:
            print("🛑 DEV MODE active — keeping browser open for inspection.")
            print("Close the browser window manually to exit.")
            await asyncio.sleep(600)

        await browser.close()
        print("✅ Done!")


if __name__ == "__main__":
    import sys
    from datetime import timedelta

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Program interrupted by user. Exiting...")
        sys.exit(0)