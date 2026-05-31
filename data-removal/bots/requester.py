"""
bots/requester.py — Bot 3: Requester (Home Assistant addon edition)

No dll_fix needed — running on Linux in Docker.
Browser always runs headless in the addon container.
"""

import asyncio
import os
import sys
import random
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import db

HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

# ── Active user context ───────────────────────────────────────────────────── #
FIRST      = os.environ.get("USER_FIRST_NAME", "")
LAST       = os.environ.get("USER_LAST_NAME", "")
CITY       = os.environ.get("USER_CITY", "")
STATE      = os.environ.get("USER_STATE", "")
STATE_FULL = os.environ.get("USER_STATE_FULL", "")
EMAIL      = os.environ.get("USER_EMAIL", "")
PHONE      = os.environ.get("USER_PHONE", "")


def _set_user(user: dict | None) -> None:
    global FIRST, LAST, CITY, STATE, STATE_FULL, EMAIL, PHONE
    if user:
        FIRST      = user.get("first_name", "")
        LAST       = user.get("last_name", "")
        CITY       = user.get("city", "")
        STATE      = user.get("state", "")
        STATE_FULL = user.get("state_full", "")
        EMAIL      = user.get("email", "")
        PHONE      = user.get("phone", "")
    else:
        FIRST      = os.environ.get("USER_FIRST_NAME", "")
        LAST       = os.environ.get("USER_LAST_NAME", "")
        CITY       = os.environ.get("USER_CITY", "")
        STATE      = os.environ.get("USER_STATE", "")
        STATE_FULL = os.environ.get("USER_STATE_FULL", "")
        EMAIL      = os.environ.get("USER_EMAIL", "")
        PHONE      = os.environ.get("USER_PHONE", "")


PAGE_TIMEOUT = 30_000

_HEADLESS_NOTE = (
    "Note: The browser runs headlessly in this Home Assistant addon. "
    "Complete any remaining steps manually by visiting the site in your browser."
)


async def make_page(playwright):
    browser = await playwright.chromium.launch(headless=HEADLESS)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    page = await context.new_page()
    return browser, page


async def random_delay(min_s=1.0, max_s=3.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


# ── Site-specific requester functions ──────────────────────────────────────── #

async def request_whitepages(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.whitepages.com/suppression-requests", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        name_input = await page.query_selector('input[name="name"], input[placeholder*="Name"]')
        if name_input:
            await name_input.fill(f"{FIRST} {LAST}")
            await random_delay(0.5, 1)

        state_input = await page.query_selector('input[name="state"], input[placeholder*="State"]')
        if state_input:
            await state_input.fill(STATE_FULL)

        search_btn = await page.query_selector('button[type="submit"], button:has-text("Search")')
        if search_btn:
            await search_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 4)

        return {
            "success": True,
            "method": "form",
            "confirmation": False,
            "notes": (
                f"Whitepages suppression page was loaded for '{FIRST} {LAST}' in {STATE}.\n"
                "⚠️  ACTION REQUIRED: Whitepages requires phone number verification.\n"
                f"1. Visit whitepages.com/suppression-requests in your browser\n"
                f"2. Find your listing for '{FIRST} {LAST}' in {STATE}\n"
                "3. Click 'Remove Me'\n"
                "4. Enter the phone number listed on your profile\n"
                "5. Answer the automated verification call or enter the SMS code\n\n"
                f"{_HEADLESS_NOTE}"
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error navigating to Whitepages opt-out: {e}",
        }


async def request_spokeo(page, scan: dict) -> dict:
    profile_url = scan.get("profile_url", "")
    try:
        await page.goto("https://www.spokeo.com/optout", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        url_input = await page.query_selector(
            'input[name="listing_url"], input[placeholder*="URL"], input[type="url"]'
        )
        if url_input and profile_url:
            await url_input.fill(profile_url)
            await random_delay(0.5, 1)

        email_input = await page.query_selector('input[type="email"], input[name="email"]')
        if email_input:
            await email_input.fill(EMAIL)
            await random_delay(0.5, 1)

        submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 3)

        content = await page.inner_text("body")
        confirmed = any(
            phrase in content.lower()
            for phrase in ["check your email", "confirmation sent", "opt out request received"]
        )

        return {
            "success": True,
            "method": "form",
            "confirmation": confirmed,
            "notes": (
                f"Spokeo opt-out form submitted for {profile_url or 'your listing'}.\n"
                f"📧 Check {EMAIL} for a verification email from Spokeo.\n"
                "Click the link in the email to complete the opt-out.\n"
                "Spokeo typically removes records within 24–48 hours."
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error submitting Spokeo opt-out: {e}",
        }


async def request_beenverified(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.beenverified.com/app/optout/search", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        first_input = await page.query_selector('input[name="firstName"], input[placeholder*="First"]')
        if first_input:
            await first_input.fill(FIRST)
            await random_delay(0.3, 0.8)

        last_input = await page.query_selector('input[name="lastName"], input[placeholder*="Last"]')
        if last_input:
            await last_input.fill(LAST)
            await random_delay(0.3, 0.8)

        state_sel = await page.query_selector('select[name="state"]')
        if state_sel:
            await state_sel.select_option(value=STATE)

        submit_btn = await page.query_selector('button[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 4)

        return {
            "success": True,
            "method": "form",
            "confirmation": False,
            "notes": (
                f"BeenVerified search submitted for {FIRST} {LAST} in {STATE}.\n"
                "⚠️  ACTION REQUIRED:\n"
                "1. Visit beenverified.com/app/optout/search in your browser\n"
                "2. Find YOUR record in the results\n"
                "3. Click 'Opt Out of This Record'\n"
                f"4. Enter your email address ({EMAIL}) when prompted\n"
                "5. Check your inbox for the BeenVerified verification email\n"
                "6. Click the link to complete the removal\n\n"
                f"{_HEADLESS_NOTE}"
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with BeenVerified opt-out: {e}",
        }


async def request_mylife(page, scan: dict) -> dict:
    profile_url = scan.get("profile_url", "(profile URL from your scan)")
    email_body = (
        f"To: optout@mylife.com\n"
        f"Subject: Data Removal Request — {FIRST} {LAST}\n\n"
        f"Hello MyLife Privacy Team,\n\n"
        f"I am writing to request the removal of my personal information from "
        f"MyLife.com under applicable privacy laws (CCPA / state privacy rights).\n\n"
        f"My details:\n"
        f"  Full name:  {FIRST} {LAST}\n"
        f"  City/State: {CITY}, {STATE_FULL}\n"
        f"  Email:      {EMAIL}\n"
        f"  Profile URL: {profile_url}\n\n"
        f"Please remove all records associated with me from your website and "
        f"ensure my information is not re-added in the future.\n\n"
        f"I expect confirmation of this removal within 30 days as required by law.\n\n"
        f"Thank you,\n"
        f"{FIRST} {LAST}\n"
    )

    return {
        "success": True,
        "method": "email",
        "confirmation": False,
        "notes": (
            "MyLife removal requires sending an email to optout@mylife.com.\n"
            "The email text has been generated — copy it from the 'Email Text' "
            "section below, paste it into your email client, and send it.\n"
            "MyLife typically responds within 30 days."
        ),
        "email_text": email_body,
    }


async def request_intelius(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.intelius.com/opt-out/submit/", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        for sel, value in [
            ('input[name="firstName"], input[placeholder*="First"]', FIRST),
            ('input[name="lastName"], input[placeholder*="Last"]', LAST),
            ('input[name="city"], input[placeholder*="City"]', CITY),
            ('input[type="email"], input[name="email"]', EMAIL),
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                await random_delay(0.3, 0.7)

        state_sel = await page.query_selector('select[name="state"]')
        if state_sel:
            await state_sel.select_option(value=STATE)

        submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 3)

        content = await page.inner_text("body")
        confirmed = any(
            p in content.lower()
            for p in ["check your email", "confirmation", "request received", "submitted"]
        )

        return {
            "success": True,
            "method": "form",
            "confirmation": confirmed,
            "notes": (
                f"Intelius opt-out form submitted for {FIRST} {LAST}.\n"
                f"📧 Check {EMAIL} for a verification email.\n"
                "Click the link to complete removal (takes up to 72 hours)."
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with Intelius opt-out: {e}",
        }


async def request_peoplefinder(page, scan: dict) -> dict:
    profile_url = scan.get("profile_url", "")
    try:
        await page.goto("https://www.peoplefinder.com/optout.php", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        url_input = await page.query_selector('input[name="record_url"], input[type="url"], input[type="text"]')
        if url_input and profile_url:
            await url_input.fill(profile_url)
            await random_delay(0.5, 1)

        submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 3)

        content = await page.inner_text("body")
        confirmed = "opt out" in content.lower() and (
            "success" in content.lower() or "submitted" in content.lower()
        )

        return {
            "success": True,
            "method": "form",
            "confirmation": confirmed,
            "notes": (
                f"PeopleFinder opt-out submitted for:\n{profile_url}\n"
                "No email verification required. Removal usually takes 24–48 hours."
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with PeopleFinder opt-out: {e}",
        }


async def request_zabasearch(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.zabasearch.com/block_records/", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        for sel, value in [
            ('input[name="firstName"], input[placeholder*="First"]', FIRST),
            ('input[name="lastName"], input[placeholder*="Last"]', LAST),
            ('input[name="city"], input[placeholder*="City"]', CITY),
            ('input[type="email"], input[name="email"]', EMAIL),
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                await random_delay(0.3, 0.7)

        state_sel = await page.query_selector('select[name="state"]')
        if state_sel:
            await state_sel.select_option(value=STATE)

        submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 3)

        content = await page.inner_text("body")
        confirmed = "email" in content.lower() and "confirm" in content.lower()

        return {
            "success": True,
            "method": "form",
            "confirmation": confirmed,
            "notes": (
                f"ZabaSearch block-records form submitted for {FIRST} {LAST}.\n"
                f"📧 Check {EMAIL} for a verification email from ZabaSearch.\n"
                "Click the confirmation link to finalise removal."
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with ZabaSearch opt-out: {e}",
        }


async def request_fastpeoplesearch(page, scan: dict) -> dict:
    profile_url = scan.get("profile_url", "")
    try:
        await page.goto("https://www.fastpeoplesearch.com/removal", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        url_input = await page.query_selector('input[name="url"], input[type="url"], input[placeholder*="URL"]')
        if url_input and profile_url:
            await url_input.fill(profile_url)
            await random_delay(0.5, 1)

        email_input = await page.query_selector('input[type="email"], input[name="email"]')
        if email_input:
            await email_input.fill(EMAIL)
            await random_delay(0.5, 1)

        submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
        if submit_btn:
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 3)

        content = await page.inner_text("body")
        confirmed = any(p in content.lower() for p in ["check your email", "removal request", "submitted"])

        return {
            "success": True,
            "method": "form",
            "confirmation": confirmed,
            "notes": (
                f"FastPeopleSearch removal submitted for:\n{profile_url}\n"
                f"📧 Check {EMAIL} for a confirmation email.\n"
                "Records are usually removed within a few hours."
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with FastPeopleSearch opt-out: {e}",
        }


async def request_truthfinder(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.truthfinder.com/opt-out/", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        for sel, value in [
            ('input[name="firstName"], input[placeholder*="First"]', FIRST),
            ('input[name="lastName"], input[placeholder*="Last"]', LAST),
            ('input[name="city"], input[placeholder*="City"]', CITY),
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                await random_delay(0.3, 0.7)

        state_sel = await page.query_selector('select[name="state"]')
        if state_sel:
            await state_sel.select_option(value=STATE)

        search_btn = await page.query_selector('button[type="submit"]')
        if search_btn:
            await search_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 4)

        return {
            "success": True,
            "method": "form",
            "confirmation": False,
            "notes": (
                f"TruthFinder opt-out search submitted for {FIRST} {LAST} in {STATE}.\n"
                "⚠️  ACTION REQUIRED:\n"
                "1. Visit truthfinder.com/opt-out/ in your browser\n"
                "2. Find your record\n"
                "3. Click 'Remove Record'\n"
                f"4. Enter your email address ({EMAIL})\n"
                "5. Check your inbox for TruthFinder's verification email\n"
                "6. Click the link — removal takes 24–48 hours\n\n"
                f"{_HEADLESS_NOTE}"
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": f"Error with TruthFinder opt-out: {e}",
        }


async def request_radaris(page, scan: dict) -> dict:
    profile_url = scan.get("profile_url", "(profile URL from your scan)")
    email_body = (
        f"To: privacy@radaris.com\n"
        f"Subject: Profile Removal Request — {FIRST} {LAST}\n\n"
        f"Hello Radaris Privacy Team,\n\n"
        f"I am requesting the immediate removal of my personal profile from "
        f"Radaris.com under my rights under applicable privacy law.\n\n"
        f"My details:\n"
        f"  Full name:  {FIRST} {LAST}\n"
        f"  City/State: {CITY}, {STATE_FULL}\n"
        f"  Email:      {EMAIL}\n"
        f"  Profile URL: {profile_url}\n\n"
        f"Please remove this record and confirm removal to the email address above.\n\n"
        f"Thank you,\n{FIRST} {LAST}\n"
    )

    try:
        await page.goto("https://radaris.com/page/how-to-remove-information", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        return {
            "success": True,
            "method": "email",
            "confirmation": False,
            "notes": (
                "Radaris removal requires either:\n"
                "  A) Creating a free Radaris account, claiming your profile, "
                "     then selecting Remove Profile\n"
                "  B) Emailing privacy@radaris.com — the email template is ready below\n\n"
                "The email option is easier and does not require creating an account."
            ),
            "email_text": email_body,
        }

    except Exception as e:
        return {
            "success": False,
            "method": "email",
            "confirmation": False,
            "notes": f"Error navigating to Radaris removal page: {e}",
            "email_text": email_body,
        }


async def request_anywho(page, scan: dict) -> dict:
    try:
        await page.goto("https://www.anywho.com/opt-out", timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
        await random_delay()

        # ── Step 1: fill the search form ──────────────────────────────────── #
        for sel, value in [
            ('input[name="firstName"], input[placeholder*="First"], input[id*="first"]', FIRST),
            ('input[name="lastName"],  input[placeholder*="Last"],  input[id*="last"]',  LAST),
            ('input[name="city"],      input[placeholder*="City"],  input[id*="city"]',  CITY),
        ]:
            el = await page.query_selector(sel)
            if el:
                await el.fill(value)
                await random_delay(0.3, 0.7)

        state_sel = await page.query_selector('select[name="state"], select[id*="state"]')
        if state_sel:
            await state_sel.select_option(value=STATE)
            await random_delay(0.3, 0.5)

        search_btn = await page.query_selector(
            'button[type="submit"], input[type="submit"], button:has-text("Search"), button:has-text("Find")'
        )
        if search_btn:
            await search_btn.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
            await random_delay(2, 4)

        # ── Step 2: find and click Remove on the matching listing ─────────── #
        clicked_remove = False

        # Try finding a result row that contains our name and clicking its Remove button
        result_rows = await page.query_selector_all(
            '.record, .result, .listing, [class*="result"], [class*="record"], [class*="person"], li'
        )
        for row in result_rows:
            text = (await row.inner_text()).lower()
            if LAST.lower() in text and FIRST.lower() in text:
                remove = await row.query_selector(
                    'button:has-text("Remove"), a:has-text("Remove"), input[value*="Remove"]'
                )
                if remove:
                    await remove.click()
                    await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
                    await random_delay(2, 3)
                    clicked_remove = True
                    break

        # Fallback: click the first visible Remove button on the page
        if not clicked_remove:
            remove = await page.query_selector(
                'button:has-text("Remove"), a:has-text("Remove this record"), '
                'a:has-text("Remove My Listing"), input[value*="Remove"]'
            )
            if remove:
                await remove.click()
                await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
                await random_delay(2, 3)
                clicked_remove = True

        # ── Step 3: enter email and submit the removal form ───────────────── #
        submitted_email = False
        email_input = await page.query_selector('input[type="email"], input[name="email"], input[id*="email"]')
        if email_input and EMAIL:
            await email_input.fill(EMAIL)
            await random_delay(0.5, 1)

            submit_btn = await page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                await submit_btn.click()
                await page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)
                await random_delay(2, 3)
                submitted_email = True

        content = await page.inner_text("body")
        confirmed = any(
            p in content.lower()
            for p in ["check your email", "confirmation", "submitted", "request received", "verify"]
        )

        if submitted_email:
            notes = (
                f"AnyWho opt-out submitted for {FIRST} {LAST} in {CITY}, {STATE}.\n"
                f"📧 Check {EMAIL} for a verification email from AnyWho.\n"
                "Click the link in the email to complete the opt-out.\n"
                "Removal typically takes 3–7 business days.\n\n"
                "Note: AnyWho is part of the Intelius network — opting out of "
                "Intelius (site #5) should also cover AnyWho."
            )
        else:
            notes = (
                f"AnyWho opt-out page loaded for {FIRST} {LAST} in {CITY}, {STATE}.\n"
                "⚠️  ACTION REQUIRED — the bot could not fully complete the form:\n"
                "1. Visit anywho.com/opt-out in your browser\n"
                "2. Enter your name, city, and state and click Search\n"
                "3. Find your listing and click Remove\n"
                f"4. Enter your email ({EMAIL}) and submit\n"
                "5. Click the verification link in your email\n\n"
                f"{_HEADLESS_NOTE}"
            )

        return {
            "success": clicked_remove or submitted_email,
            "method": "form",
            "confirmation": confirmed,
            "notes": notes,
        }

    except Exception as e:
        return {
            "success": False,
            "method": "form",
            "confirmation": False,
            "notes": (
                f"Error during AnyWho opt-out: {e}\n"
                "Manual steps:\n"
                "1. Go to anywho.com/opt-out\n"
                "2. Enter your name, city, and state\n"
                "3. Select your listing and click 'Remove'\n"
                f"4. Enter your email ({EMAIL}) and submit\n"
                "5. Click the verification link in your email"
            ),
        }


async def request_generic(page, scan: dict) -> dict:
    opt_out_url  = scan.get("opt_out_url", "")
    site_name    = scan.get("site_name", "this site")
    instructions = scan.get("opt_out_instructions", "")
    profile_url  = scan.get("profile_url", "")

    navigated = False
    if opt_out_url:
        try:
            await page.goto(opt_out_url, timeout=PAGE_TIMEOUT)
            await page.wait_for_load_state("domcontentloaded", timeout=PAGE_TIMEOUT)
            await random_delay()
            navigated = True
        except Exception:
            pass

    parts = [f"No automated opt-out script exists for {site_name} yet.\n"]

    if navigated:
        parts.append(f"The opt-out page was loaded: {opt_out_url}\n")
    elif opt_out_url:
        parts.append(f"Opt-out URL: {opt_out_url}\n")

    if profile_url:
        parts.append(f"Your profile: {profile_url}\n")

    if instructions:
        parts.append("Opt-out instructions:")
        parts.append(instructions)
    elif opt_out_url:
        parts.append("Manual steps:")
        parts.append(f"1. Visit {opt_out_url}")
        parts.append("2. Search for your name and location")
        parts.append("3. Follow the site's removal/opt-out process")
        parts.append("4. Click the verification link in your email if prompted")
    else:
        parts.append(f"Visit {site_name}'s website and look for a Privacy / Data Removal / Opt-Out link.")

    parts.append("\nOnce removed, click 'Mark Removed' on the dashboard.")

    return {
        "success": navigated,
        "method": "form",
        "confirmation": False,
        "notes": "\n".join(parts),
    }


# ── Map site name → requester function ──────────────────────────────────── #
REQUESTER_MAP = {
    "Whitepages":       request_whitepages,
    "Spokeo":           request_spokeo,
    "BeenVerified":     request_beenverified,
    "MyLife":           request_mylife,
    "Intelius":         request_intelius,
    "PeopleFinder":     request_peoplefinder,
    "ZabaSearch":       request_zabasearch,
    "FastPeopleSearch": request_fastpeoplesearch,
    "TruthFinder":      request_truthfinder,
    "Radaris":          request_radaris,
    "AnyWho":           request_anywho,
}


async def submit_removal_request(scan_id: int, user: dict | None = None) -> dict:
    _set_user(user)
    scan = db.get_scan(scan_id)
    if not scan:
        return {"success": False, "notes": f"Scan ID {scan_id} not found."}

    site_name    = scan["site_name"]
    requester_fn = REQUESTER_MAP.get(site_name, request_generic)

    print(f"[Requester] Submitting opt-out for {site_name} (scan #{scan_id})…")

    async with async_playwright() as p:
        browser, page = await make_page(p)
        try:
            result = await requester_fn(page, scan)
        finally:
            await browser.close()

    db.insert_request(
        scan_id=scan_id,
        method=result.get("method", "form"),
        confirmation=result.get("confirmation", False),
        notes=result.get("notes", ""),
        email_text=result.get("email_text"),
    )

    icon = "✅" if result["success"] else "❌"
    print(f"[Requester] {icon} {site_name}: {'submitted' if result['success'] else 'failed'}")
    return result


async def submit_all_pending(user: dict | None = None) -> list[dict]:
    all_scans = db.get_all_scans(user_id=user["id"] if user else None)
    pending   = [s for s in all_scans if s["status"] == "found"]

    if not pending:
        print("[Requester] No scans in 'found' status — nothing to request.")
        return []

    results = []
    for scan in pending:
        result = await submit_removal_request(scan["id"], user)
        results.append(result)
        await asyncio.sleep(random.uniform(3, 6))

    return results


if __name__ == "__main__":
    asyncio.run(submit_all_pending())
