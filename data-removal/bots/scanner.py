"""
bots/scanner.py — Bot 1: Scanner (Home Assistant addon edition)

No dll_fix needed — running on Linux in Docker.
HEADLESS is always true in the container.
"""

import asyncio
import json
import os
import random
import sys
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


def _set_user(user: dict | None) -> None:
    global FIRST, LAST, CITY, STATE, STATE_FULL, EMAIL
    if user:
        FIRST      = user.get("first_name", "")
        LAST       = user.get("last_name", "")
        CITY       = user.get("city", "")
        STATE      = user.get("state", "")
        STATE_FULL = user.get("state_full", "")
        EMAIL      = user.get("email", "")
    else:
        FIRST      = os.environ.get("USER_FIRST_NAME", "")
        LAST       = os.environ.get("USER_LAST_NAME", "")
        CITY       = os.environ.get("USER_CITY", "")
        STATE      = os.environ.get("USER_STATE", "")
        STATE_FULL = os.environ.get("USER_STATE_FULL", "")
        EMAIL      = os.environ.get("USER_EMAIL", "")


PAGE_TIMEOUT   = 30_000
RESULT_TIMEOUT = 15_000


async def make_browser_context(playwright):
    browser = await playwright.chromium.launch(headless=HEADLESS)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/Chicago",
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


async def random_delay(min_s: float = 2.0, max_s: float = 5.0):
    await asyncio.sleep(random.uniform(min_s, max_s))


def profile_in_page(content: str, first: str, last: str, city: str, state: str) -> bool:
    c = content.lower()
    name_match = first.lower() in c and last.lower() in c
    loc_match  = city.lower() in c or state.lower() in c or STATE_FULL.lower() in c
    return name_match and loc_match


def extract_data_fields(content: str, first: str, last: str) -> dict:
    c = content.lower()
    fields = {}
    if first.lower() in c and last.lower() in c:
        fields["name"] = f"{first} {last}"
    if CITY.lower() in c:
        fields["city"] = CITY
    if STATE.lower() in c or STATE_FULL.lower() in c:
        fields["state"] = STATE
    return fields


# ── Site-specific scanner functions ─────────────────────────────────────── #

async def scan_whitepages(page) -> dict:
    name_slug  = f"{FIRST}-{LAST}".lower().replace(" ", "-")
    state_slug = STATE.upper()
    url = f"https://www.whitepages.com/name/{name_slug}/{state_slug}"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "access denied" in content.lower() or "robot" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_spokeo(page) -> dict:
    first_clean = FIRST.replace(" ", "-")
    last_clean  = LAST.replace(" ", "-")
    state_slug  = STATE.upper()
    url = f"https://www.spokeo.com/{first_clean}-{last_clean}/{state_slug}"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "please verify you are a human" in content.lower() or "captcha" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            profile_link = await page.query_selector("a[href*='/search#age=']") or \
                           await page.query_selector(".card-link")
            profile_url = None
            if profile_link:
                profile_url = await profile_link.get_attribute("href")
                if profile_url and not profile_url.startswith("http"):
                    profile_url = "https://www.spokeo.com" + profile_url
            return {
                "found": True,
                "profile_url": profile_url or page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_beenverified(page) -> dict:
    url = "https://www.beenverified.com/app/optout/search"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("domcontentloaded", timeout=RESULT_TIMEOUT)
        await random_delay(1, 2)

        await page.fill('input[name="firstName"], input[placeholder*="First"]', FIRST)
        await random_delay(0.5, 1)
        await page.fill('input[name="lastName"], input[placeholder*="Last"]', LAST)
        await random_delay(0.5, 1)

        state_selector = 'select[name="state"], select[id*="state"]'
        if await page.query_selector(state_selector):
            await page.select_option(state_selector, value=STATE)

        await page.click('button[type="submit"], input[type="submit"]')
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_mylife(page) -> dict:
    url = f"https://www.mylife.com/pub/search?search[name]={FIRST}+{LAST}"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "sign in" in content.lower() and "create account" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_intelius(page) -> dict:
    url = (
        f"https://www.intelius.com/search/?search_type=person"
        f"&qf={FIRST}&qln={LAST}&qc={CITY}&qs={STATE}"
    )
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "captcha" in content.lower() or "access denied" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_peoplefinder(page) -> dict:
    url = (
        f"https://www.peoplefinder.com/people-search/"
        f"?fname={FIRST}&lname={LAST}&state={STATE}"
    )
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "access denied" in content.lower() or "cloudflare" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            profile_el = await page.query_selector("a.card-block, a[href*='/people/']")
            profile_url = None
            if profile_el:
                profile_url = await profile_el.get_attribute("href")
                if profile_url and not profile_url.startswith("http"):
                    profile_url = "https://www.peoplefinder.com" + profile_url
            return {
                "found": True,
                "profile_url": profile_url or page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_zabasearch(page) -> dict:
    first_enc = FIRST.replace(" ", "+")
    last_enc  = LAST.replace(" ", "+")
    url = f"https://www.zabasearch.com/people/{first_enc}+{last_enc}/{STATE}/"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_fastpeoplesearch(page) -> dict:
    first_slug = FIRST.replace(" ", "-")
    last_slug  = LAST.replace(" ", "-")
    state_slug = STATE.upper()
    url = f"https://www.fastpeoplesearch.com/name/{first_slug}-{last_slug}_{state_slug}"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "captcha" in content.lower() or "rate limit" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            profile_el = await page.query_selector("a.card-block, a[href*='/name/']")
            profile_url = None
            if profile_el:
                href = await profile_el.get_attribute("href")
                if href and not href.startswith("http"):
                    profile_url = "https://www.fastpeoplesearch.com" + href
                else:
                    profile_url = href
            return {
                "found": True,
                "profile_url": profile_url or page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_truthfinder(page) -> dict:
    url = (
        f"https://www.truthfinder.com/people-search/"
        f"?firstName={FIRST}&lastName={LAST}&state={STATE}&city={CITY}"
    )
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "captcha" in content.lower() or "verify you are human" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


async def scan_radaris(page) -> dict:
    url = f"https://radaris.com/p/{FIRST}/{LAST}/"
    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        if "access denied" in content.lower() or "cloudflare" in content.lower():
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            profile_el = await page.query_selector("a[href*='/ng/search/people/p/']")
            profile_url = None
            if profile_el:
                href = await profile_el.get_attribute("href")
                if href and not href.startswith("http"):
                    profile_url = "https://radaris.com" + href
                else:
                    profile_url = href
            return {
                "found": True,
                "profile_url": profile_url or page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


# ── Generic scanner ──────────────────────────────────────────────────────── #

def _build_search_url(template: str) -> str:
    subs = {
        "first":      FIRST,
        "last":       LAST,
        "city":       CITY.replace(" ", "+"),
        "state":      STATE,
        "state_full": STATE_FULL,
        "first_last": f"{FIRST}-{LAST}".lower().replace(" ", "-"),
        "name":       f"{FIRST}+{LAST}",
    }
    try:
        return template.format_map(subs)
    except (KeyError, ValueError):
        return template.split("{")[0].rstrip("/?")


async def scan_generic(page, site: dict) -> dict:
    from opt_out_db import get_site_config

    site_name = site.get("name", "")
    config = get_site_config(site_name) or {}
    template = config.get("search_url_template") or site.get("search_url_template") or site.get("url", "")

    if not template:
        return {
            "found": False, "profile_url": None, "data_fields": {}, "status": "error",
            "error": "No search_url_template configured for this site",
        }

    url = _build_search_url(template)

    try:
        await page.goto(url, timeout=PAGE_TIMEOUT)
        await page.wait_for_load_state("networkidle", timeout=RESULT_TIMEOUT)
        await random_delay()
        content = await page.inner_text("body")

        blocked_phrases = [
            "access denied", "captcha", "robot", "cloudflare",
            "too many requests", "rate limit", "verify you are human",
        ]
        if any(p in content.lower() for p in blocked_phrases):
            return {"found": False, "profile_url": None, "data_fields": {}, "status": "blocked"}

        if profile_in_page(content, FIRST, LAST, CITY, STATE):
            return {
                "found": True,
                "profile_url": page.url,
                "data_fields": extract_data_fields(content, FIRST, LAST),
                "status": "found",
            }
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "not_found"}

    except PlaywrightTimeout:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": "Timeout"}
    except Exception as e:
        return {"found": False, "profile_url": None, "data_fields": {}, "status": "error", "error": str(e)}


SCANNER_MAP = {
    "Whitepages":       scan_whitepages,
    "Spokeo":           scan_spokeo,
    "BeenVerified":     scan_beenverified,
    "MyLife":           scan_mylife,
    "Intelius":         scan_intelius,
    "PeopleFinder":     scan_peoplefinder,
    "ZabaSearch":       scan_zabasearch,
    "FastPeopleSearch": scan_fastpeoplesearch,
    "TruthFinder":      scan_truthfinder,
    "Radaris":          scan_radaris,
}


async def scan_single_site(site: dict, user: dict | None = None) -> dict:
    _set_user(user)

    site_name  = site["name"]
    site_id    = site["id"]
    user_id    = user["id"] if user else None
    scanner_fn = SCANNER_MAP.get(site_name)

    label = f" [{user['display_name']}]" if user else ""
    print(f"[Scanner]{label} Scanning {site_name}{'  (generic)' if not scanner_fn else ''}…")

    async with async_playwright() as p:
        browser, context = await make_browser_context(p)
        page = await context.new_page()
        try:
            if scanner_fn:
                result = await scanner_fn(page)
            else:
                result = await scan_generic(page, site)
        finally:
            await browser.close()

    scan_id = db.insert_scan(
        site_id=site_id,
        profile_found=result["found"],
        profile_url=result.get("profile_url"),
        data_fields=result.get("data_fields"),
        status=result["status"],
        user_id=user_id,
    )
    result["scan_id"] = scan_id
    result["site"]    = site_name

    status_icon = "🔴" if result["found"] else ("⚠️" if result["status"] == "blocked" else "✅")
    print(f"[Scanner] {status_icon} {site_name}: {result['status']}")
    return result


async def run_all_scans(
    site_ids: list[int] | None = None,
    user: dict | None = None,
    progress_callback=None,
) -> list[dict]:
    sites = db.get_all_sites()
    if site_ids:
        sites = [s for s in sites if s["id"] in site_ids]

    sites = [s for s in sites if s.get("enabled", 1)]

    results = []
    total = len(sites)
    for i, site in enumerate(sites):
        if progress_callback:
            progress_callback(i + 1, total, site["name"])
        result = await scan_single_site(site, user=user)
        results.append(result)
        if i < total - 1:
            delay = random.uniform(3, 7)
            print(f"[Scanner] Waiting {delay:.1f}s before next site…")
            await asyncio.sleep(delay)

    found_count = sum(1 for r in results if r.get("found"))
    user_label  = user["display_name"] if user else "env user"
    print(f"\n[Scanner] Done for {user_label}. Found on {found_count}/{len(results)} sites.")
    return results


if __name__ == "__main__":
    asyncio.run(run_all_scans())
