"""
LinkedIn Job Application & Networking Bot — Playwright Edition
===============================================================
A semi-automated tool to:
  1. Search and apply to jobs (Easy Apply)
  2. Find HR/recruiters and send connection requests with personalized notes
  3. Track all activity in a local SQLite database

USAGE:
  python linkedin_bot.py --mode apply     # Job search & apply mode
  python linkedin_bot.py --mode connect   # HR/recruiter connect mode
  python linkedin_bot.py --mode report    # Show activity report
  python linkedin_bot.py --mode all       # Run both apply + connect
  python linkedin_bot.py --headless       # Run without visible browser
"""

import argparse
import json
import logging
import os
import random
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeout

# ─── Paths (repo-root so script works from any cwd) ─────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "settings.json"
ENV_PATH = REPO_ROOT / ".env"
LOG_DIR = REPO_ROOT / "logs"
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "tracker.db"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

# ─── Logging Setup ────────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        log.error(f"Config not found: {CONFIG_PATH}. Run setup.py first.")
        raise FileNotFoundError(CONFIG_PATH)
    load_dotenv(ENV_PATH)
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    # Credentials and profile from .env (never from settings.json)
    config["credentials"] = {
        "email": os.environ.get("LINKEDIN_EMAIL", "").strip(),
        "password": os.environ.get("LINKEDIN_PASSWORD", "").strip(),
    }
    config["profile"] = {
        "first_name": os.environ.get("PROFILE_FIRST_NAME", "").strip(),
        "last_name": os.environ.get("PROFILE_LAST_NAME", "").strip(),
        "phone": os.environ.get("PROFILE_PHONE", "").strip(),
        "target_role": os.environ.get("PROFILE_TARGET_ROLE", "").strip(),
        "years_experience": os.environ.get("PROFILE_YEARS_EXPERIENCE", "").strip(),
    }
    return config


# ─── Database ─────────────────────────────────────────────────────────────────
DATA_DIR.mkdir(exist_ok=True)


def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title   TEXT,
            company     TEXT,
            job_url     TEXT UNIQUE,
            status      TEXT DEFAULT 'Applied',
            applied_at  TEXT,
            notes       TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS connections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT,
            company         TEXT,
            profile_url     TEXT UNIQUE,
            message_sent    TEXT,
            status          TEXT DEFAULT 'Pending',
            connected_at    TEXT
        )
    """)
    conn.commit()
    conn.close()
    log.info("Database initialized.")


def log_application(job_title, company, job_url, notes=""):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO applications (job_title, company, job_url, applied_at, notes) VALUES (?, ?, ?, ?, ?)",
            (job_title, company, job_url, datetime.now().isoformat(), notes),
        )
        conn.commit()
        log.info(f"[DB] Logged application: {job_title} @ {company}")
    finally:
        conn.close()


def log_connection(name, company, profile_url, message):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        c.execute(
            "INSERT OR IGNORE INTO connections (name, company, profile_url, message_sent, connected_at) VALUES (?, ?, ?, ?, ?)",
            (name, company, profile_url, message, datetime.now().isoformat()),
        )
        conn.commit()
        log.info(f"[DB] Logged connection: {name} @ {company}")
    finally:
        conn.close()


def print_report():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    print("\n" + "=" * 60)
    print("  📊  LINKEDIN BOT — ACTIVITY REPORT")
    print("=" * 60)

    c.execute("SELECT COUNT(*) FROM applications")
    print(f"\n  📋 Total Job Applications : {c.fetchone()[0]}")
    c.execute("SELECT job_title, company, status, applied_at FROM applications ORDER BY applied_at DESC LIMIT 10")
    for r in c.fetchall():
        print(f"    • [{r[2]}] {r[0]} @ {r[1]}  ({r[3][:10]})")

    c.execute("SELECT COUNT(*) FROM connections")
    print(f"\n  🤝 Total Connection Requests: {c.fetchone()[0]}")
    c.execute("SELECT name, company, status, connected_at FROM connections ORDER BY connected_at DESC LIMIT 10")
    for r in c.fetchall():
        print(f"    • [{r[3]}] {r[0]} @ {r[2]}  ({r[4][:10]})")

    print("\n" + "=" * 60 + "\n")
    conn.close()


# ─── Human-like Helpers ───────────────────────────────────────────────────────
def human_delay(min_s: float = 1.5, max_s: float = 3.5):
    time.sleep(random.uniform(min_s, max_s))


def scroll_page(page: Page, times: int = 3):
    for _ in range(times):
        page.evaluate("window.scrollBy(0, 600)")
        human_delay(0.5, 1.2)


def safe_click(page: Page, selector: str, timeout: int = 5000) -> bool:
    try:
        page.locator(selector).first.click(timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


def element_exists(locator_or_page, selector: str, timeout: int = 3000) -> bool:
    try:
        locator_or_page.locator(selector).first.wait_for(state="visible", timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


def first_existing_locator(locator_or_page, selectors, timeout: int = 3000):
    """
    Try a list of selectors and return the first Locator that becomes visible.
    This helps support both premium and non-premium LinkedIn UIs, which often
    use slightly different aria-labels / DOM structures for the same action.
    """
    for sel in selectors:
        try:
            loc = locator_or_page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return None


def first_locator_with_nth_visible(locator_or_page, selectors, nth: int = 0, timeout: int = 3000):
    """
    Try selectors and return the Locator (multi-match) for the first selector
    that has the nth element (0-based) visible.
    Useful when LinkedIn renders duplicate actions (e.g., multiple "More" buttons).
    """
    for sel in selectors:
        try:
            loc = locator_or_page.locator(sel)
            loc.nth(nth).wait_for(state="visible", timeout=timeout)
            return loc
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return None


def first_non_empty_text(locator_or_page, selectors, timeout: int = 1500) -> str:
    """
    Return the first non-empty visible inner_text found from a list of selectors.
    """
    for sel in selectors:
        try:
            loc = locator_or_page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout)
            txt = loc.inner_text(timeout=timeout).strip()
            if txt:
                return txt
        except PlaywrightTimeout:
            continue
        except Exception:
            continue
    return ""


# ─── Browser Setup ────────────────────────────────────────────────────────────
def create_browser(playwright, headless: bool = False):
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
    )
    # Mask webdriver fingerprint
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)
    return browser, context


# ─── LinkedIn Login ───────────────────────────────────────────────────────────
def linkedin_login(page: Page, email: str, password: str):
    log.info("Navigating to LinkedIn login...")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    human_delay(2, 4)

    page.locator("#username").fill(email)
    human_delay(0.5, 1.0)
    page.locator("#password").fill(password)
    human_delay(0.5, 1.0)
    page.locator("[data-litms-control-urn='login-submit']").click()
    human_delay(3, 5)

    url = page.url
    if "feed" in url or "mynetwork" in url:
        log.info("✅ Login successful.")
    elif "checkpoint" in url or "challenge" in url:
        log.warning("⚠️  LinkedIn requires verification (CAPTCHA / 2FA).")
        input("   → Complete it in the browser window, then press Enter...")
    else:
        log.warning(f"⚠️  Unexpected URL after login: {url}")
        input("   → Check the browser, then press Enter to continue...")


# ─── Job Application ──────────────────────────────────────────────────────────
def build_job_search_url(keywords: str, location: str, date_posted: str = "r604800") -> str:
    kw = keywords.replace(" ", "%20")
    loc = location.replace(" ", "%20")
    return (
        f"https://www.linkedin.com/jobs/search/?keywords={kw}"
        f"&location={loc}&f_TPR={date_posted}&f_LF=f_AL&sortBy=DD"
    )


def handle_easy_apply_modal(page: Page, config: dict) -> bool:
    profile = config["profile"]

    for step in range(4):
        human_delay(1.5, 2.5)

        # Fill phone number if empty
        phone_sel = "input[id*='phoneNumber'], input[name*='phone']"
        if element_exists(page, phone_sel, timeout=2000):
            phone_field = page.locator(phone_sel).first
            if not phone_field.input_value():
                phone_field.fill(profile.get("phone", ""))
                human_delay(0.3, 0.7)

        # Handle dropdowns
        dropdowns = page.locator("select.fb-dropdown__select").all()
        for dropdown in dropdowns:
            try:
                options = dropdown.locator("option").all()
                if len(options) > 1:
                    dropdown.select_option(index=1)
                    human_delay(0.2, 0.5)
            except Exception:
                pass

        # Submit button
        submit_sel = "button[aria-label='Submit application']"
        if element_exists(page, submit_sel, timeout=2000):
            page.locator(submit_sel).click()
            human_delay(2, 3)
            log.info("   → Application submitted!")
            safe_click(page, "button[aria-label='Dismiss']", timeout=3000)
            return True

        # Next / Review
        next_sel = "button[aria-label='Continue to next step']"
        review_sel = "button[aria-label='Review your application']"

        if element_exists(page, next_sel, timeout=2000):
            page.locator(next_sel).click()
        elif element_exists(page, review_sel, timeout=2000):
            page.locator(review_sel).click()
        else:
            safe_click(page, "button[aria-label='Dismiss']", timeout=3000)
            return False

    safe_click(page, "button[aria-label='Dismiss']", timeout=3000)
    return False


def apply_to_jobs(page: Page, config: dict):
    prefs = config["job_search"]
    max_apps = prefs.get("max_applications_per_run", 10)
    applied = 0

    for keyword in prefs["keywords"]:
        if applied >= max_apps:
            break

        url = build_job_search_url(keyword, prefs["location"], prefs.get("date_posted", "r604800"))
        log.info(f"🔍 Searching: '{keyword}' in {prefs['location']}")
        page.goto(url, wait_until="domcontentloaded")
        human_delay(3, 5)
        scroll_page(page, times=3)

        job_cards = page.locator("div.job-search-card, li.jobs-search-results__list-item").all()
        log.info(f"   Found {len(job_cards)} listings.")

        for card in job_cards:
            if applied >= max_apps:
                break
            try:
                try:
                    job_title = card.locator("h3, a.job-card-list__title").first.inner_text().strip()
                    company = card.locator("h4, a.job-card-container__company-name").first.inner_text().strip()
                except Exception:
                    job_title, company = "Unknown Role", "Unknown Company"

                card.locator("h3, a.job-card-list__title").first.click()
                human_delay(2, 3)
                job_url = page.url

                easy_apply_sel = "button.jobs-apply-button"
                if not element_exists(page, easy_apply_sel, timeout=5000):
                    log.info(f"   No Easy Apply: {job_title} — skipping.")
                    continue

                log.info(f"   Applying: {job_title} @ {company}")
                page.locator(easy_apply_sel).first.click()
                human_delay(2, 3)

                success = handle_easy_apply_modal(page, config)
                if success:
                    log_application(job_title, company, job_url)
                    applied += 1
                    log.info(f"✅ [{applied}/{max_apps}] Applied: {job_title} @ {company}")
                else:
                    log.info(f"⏭️  Skipped (complex form): {job_title}")

                human_delay(2, 4)

            except Exception as e:
                log.debug(f"   Card error: {e}")
                continue

        human_delay(5, 8)

    log.info(f"Job run complete. Applied this session: {applied}")


# ─── HR / Recruiter Connect ───────────────────────────────────────────────────
def generate_connection_note(name: str, company: str, config: dict) -> str:
    # "connection_messages": [
    #     "Hi {first_name}, I'm a {your_role} actively exploring new opportunities and would love to connect with you at {company}. Looking forward to staying in touch!",
    #     "Hello {first_name}! I came across your profile and was impressed by your work at {company}. As a {your_role} exploring exciting roles, I'd love to connect and learn more about your team.",
    #     "Hi {first_name}, hope you're doing well! I'm currently exploring {your_role} opportunities and {company} really stands out to me. Would love to connect and chat if you're open to it!",
    #     "Hey {first_name}! I admire {company}'s work and I'm actively looking for {your_role} roles. I'd love to add you to my network and learn more about opportunities there.",
    #     "Hi {first_name}, I'm a passionate {your_role} looking for my next challenge. {company} is high on my list \u2014 would love to connect and introduce myself!"
    # ]
    #temp
    templates = config.get("connection_messages", [])
    if not templates:
        return (
            f"Hi {name.split()[0]}, I came across your profile and was impressed by your work at {company}. "
            "I'd love to connect and explore potential opportunities. Thank you!"
        )
    template = random.choice(templates)
    return (
        template
        .replace("{first_name}", name.split()[0])
        # .replace("{company}", company)
        # .replace("{your_role}", config["profile"].get("target_role", "professional"))
    )

def search_hr_recruiters(page: Page, config: dict):
    """
    Search for HR/recruiters by role keyword only — no target company filter.
    Optionally scoped to a location if set in networking config.
    Paginates through multiple pages until max_connects is reached.
    """
    networking   = config.get("networking", {})
    max_connects = networking.get("max_connections_per_run", 15)
    location     = networking.get("location", config["job_search"].get("location", ""))

    # Speed tuning (reduce "waiting around" between actions)
    # - delay_multiplier < 1.0 makes the bot faster (e.g. 0.5 = ~2x faster delays)
    # - selector_timeouts_ms can reduce long waits on missing UI elements
    delay_multiplier = float(networking.get("delay_multiplier", 0.6))
    delay_multiplier = max(0.0, min(delay_multiplier, 2.0))

    def d(min_s: float, max_s: float):
        if delay_multiplier <= 0:
            return
        human_delay(min_s * delay_multiplier, max_s * delay_multiplier)

    page_wait_ms = int(networking.get("page_wait_ms", 6000))
    action_wait_ms = int(networking.get("action_wait_ms", 3500))
    quick_wait_ms = int(networking.get("quick_wait_ms", 1500))

    hr_roles = networking.get(
        "hr_keywords",
        [
            "HR Manager",
            "Recruiter",
            "Talent Acquisition",
            "People Operations",
            "HR Business Partner",
            "Technical Recruiter",
        ],
    )

    # Support both premium and non-premium search result layouts.
    # Some normal accounts render results inside a plain `ul[role='list']` with dynamic classes
    # and cards as `div[data-view-name='search-entity-result-universal-template']`.
    CARD_SELECTOR = "div[role='list'], ul[role='list'], ul.reusable-search__entity-results-list"
    CARD_SEL = (
        "div[role='list'] div[data-view-name='people-search-result'], "
        "ul.reusable-search__entity-results-list li.reusable-search__result-container, "
        "ul[role='list'] div[data-view-name='search-entity-result-universal-template'], "
        "div[data-view-name='search-entity-result-universal-template']"
    )
    NEXT_BTN_SEL = "button[data-testid='pagination-controls-next-button-visible']"

    total_connected = 0

    for role_keyword in hr_roles:
        # Each keyword gets its own max_connects quota
        connected = 0
        log.info(f"📌 Starting keyword: '{role_keyword}' (target: {max_connects} connections)")

        kw        = role_keyword.replace(" ", "%20")
        loc_param = f"&location={location.replace(' ', '%20')}" if location else ""
        base_url  = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={kw}{loc_param}&origin=FACETED_SEARCH"
        )

        log.info(f"🔍 Searching recruiters: '{role_keyword}'" + (f" in {location}" if location else ""))

        current_page = 1

        # ── Pagination loop — runs until this keyword hits max_connects ──────
        while connected < max_connects:
            paged_url = base_url + f"&page={current_page}"
            log.info(f"   Loading page {current_page}: {paged_url}")
            page.goto(paged_url, wait_until="domcontentloaded")
            d(3, 5)

            try:
                page.wait_for_selector(CARD_SELECTOR, timeout=page_wait_ms)
            except Exception:
                log.warning(f"   No results on page {current_page} for '{role_keyword}' — stopping.")
                break

            people_cards = page.locator(CARD_SEL).all()
            log.info(f"   Page {current_page}: Found {len(people_cards)} people.")

            if not people_cards:
                log.info(f"   No cards on page {current_page} — stopping pagination.")
                break

            # ── Process each card on this page ────────────────────────────────
            for i, card in enumerate(people_cards):
                if connected >= max_connects:
                    break
                try:
                    # Name (premium and normal accounts differ)
                    try:
                        name = first_non_empty_text(
                            card,
                            selectors=[
                                '[data-view-name="search-result-lockup-title"]',
                                "a[href*='/in/'] span[aria-hidden='true']",
                                "span[aria-hidden='true']",
                            ],
                            timeout=1500,
                        )
                        if not name:
                            raise ValueError("empty name")
                    except Exception:
                        continue

                    # Company
                    try:
                        headline = first_non_empty_text(
                            card,
                            selectors=[
                                "xpath=.//a/div/div[2]/p",
                                "div.entity-result__primary-subtitle",
                                "div.t-14.t-black.t-normal",
                            ],
                            timeout=1500,
                        )
                        company = headline
                        if "@" in headline:
                            after_at = headline.split("@", 1)[1].strip()
                            company = after_at.split("|", 1)[0].strip() or headline
                        if not company:
                            raise ValueError("empty company")
                    except Exception:
                        company = "their company"

                    # Profile URL
                    try:
                        profile_url = (
                            card.locator("a[href*='/in/']").first.get_attribute("href", timeout=2000)
                            or card.locator("xpath=.//a").first.get_attribute("href", timeout=2000)
                        )
                        profile_url = profile_url.split("?")[0] if profile_url else ""
                    except Exception:
                        profile_url = ""

                    log.info(f"   Card[{i}] name={name!r} company={company!r} profile_url={profile_url!r}")

                    message = generate_connection_note(name, company, config)

                    # Try multiple variants so it works for both premium & basic UIs
                    CONNECT_SELECTORS = [
                        "button:has-text('Connect')",
                        "button[aria-label^='Connect']",
                        "button[aria-label*='to connect']",
                        "button[aria-label*='Connect with']",
                        "a[aria-label*='to connect']",
                        "a[aria-label*='Connect']",
                    ]
                    FOLLOW_SELECTORS = [
                        "button[aria-label*='Follow']",
                        "button[aria-label*='Following']",
                    ]

                    connect_btn = first_existing_locator(card, CONNECT_SELECTORS, timeout=2000)
                    follow_btn = None if connect_btn else first_existing_locator(
                        card, FOLLOW_SELECTORS, timeout=2000
                    )

                    if connect_btn:
                        # ── Direct Connect ────────────────────────────────────
                        connect_btn.click()
                        d(1.5, 2.5)

                        add_note_sel = "button[aria-label='Add a note']"
                        if element_exists(page, add_note_sel, timeout=action_wait_ms):
                            page.locator(add_note_sel).click()
                            d(1, 2)
                            page.locator("textarea#custom-message").fill(message[:300])
                            d(1, 2)
                            if not safe_click(page, "button[aria-label='Send invitation']", timeout=action_wait_ms):
                                safe_click(page, "button[aria-label='Send now']", timeout=action_wait_ms)
                        else:
                            safe_click(page, "button[aria-label='Send now']", timeout=action_wait_ms)

                        d(2, 3)

                    elif follow_btn:
                        # ── Follow → open profile tab → More actions → Connect ─
                        log.info(f"   Follow button found for {name} — opening profile tab...")
                        if not profile_url:
                            log.info(f"   No profile URL for {name} — skipping follow/connect flow.")
                            continue
                        profile_page = page.context.new_page()
                        try:
                            log.info(f"   Loading profile: {profile_url}")
                            profile_page.goto(profile_url, wait_until="domcontentloaded")
                            d(2, 3)
                            log.info(f"   Profile loaded for {name}")

                            # Step 1: open the actions menu (label varies between UIs)
                            MORE_SELECTORS = [
                                "button[aria-label='More actions']",
                                "button[aria-label*='More actions']",
                                "button[aria-label*='More options']",
                                "button[aria-label*='More']",
                            ]
                            # LinkedIn sometimes renders multiple "More" buttons; the 2nd is often the real actions menu.
                            more_btn = first_locator_with_nth_visible(
                                profile_page, MORE_SELECTORS, nth=1, timeout=page_wait_ms
                            ) or first_locator_with_nth_visible(profile_page, MORE_SELECTORS, nth=0, timeout=page_wait_ms)
                            if not more_btn:
                                btns = profile_page.locator("button[aria-label]").all()
                                labels = [b.get_attribute("aria-label") for b in btns[:20]]
                                log.warning(
                                    f"   'More actions/options' not found for {name}. Buttons: {labels}"
                                )
                                raise PlaywrightTimeout("More actions/options button not found")

                            log.info(f"   Clicking actions menu button for {name}")
                            try:
                                more_btn.nth(1).click()
                            except Exception:
                                more_btn.nth(0).click()
                            d(1, 2)

                            # Step 2: Connect in dropdown (label differs across layouts)
                            # After clicking "More", the dropdown menu becomes visible as `div[role='menu']`.
                            # Scope the search to that menu to avoid matching unrelated "Connect" buttons on the page.
                            menu = first_existing_locator(
                                profile_page,
                                selectors=[
                                    "div[role='menu']",
                                    "div.artdeco-dropdown__content",
                                ],
                                timeout=action_wait_ms,
                            )

                            DROPDOWN_CONNECT_SELECTORS = [
                                # Normal accounts often render Connect as a <div aria-label="Invite X to connect">…<p>Connect</p>
                                "div[aria-label*='to connect']",
                                "button[aria-label*='Connect']",
                                "span:has-text('Connect')",
                                "p:has-text('Connect')",
                            ]
                            # Dropdown may contain duplicate Connect items; prefer the 2nd match.
                            connect_div = first_locator_with_nth_visible(
                                (menu or profile_page), DROPDOWN_CONNECT_SELECTORS, nth=1, timeout=action_wait_ms
                            ) or first_locator_with_nth_visible((menu or profile_page), DROPDOWN_CONNECT_SELECTORS, nth=0, timeout=action_wait_ms)
                            if connect_div:
                                log.info(f"   Found Connect option in dropdown")
                                try:
                                    connect_div.nth(1).click()
                                except Exception:
                                    connect_div.nth(0).click()
                                log.info(f"   Clicked Connect in dropdown")
                            else:
                                items = profile_page.locator(
                                    "div.artdeco-dropdown__content li"
                                ).all()
                                item_texts = [
                                    el.inner_text(timeout=300).strip() for el in items[:10]
                                ]
                                log.warning(
                                    f"   Connect not found in dropdown for {name}. Items: {item_texts}"
                                )
                                profile_page.keyboard.press("Escape")
                                raise Exception("Connect not found in dropdown")

                            d(1.5, 2.5)

                            # Step 3: Add note in modal
                            log.info(f"   Waiting for invite modal...")
                            add_note_sel = "button[aria-label='Add a note']"
                            if element_exists(profile_page, add_note_sel, timeout=action_wait_ms):
                                profile_page.locator(add_note_sel).click()
                                d(1, 2)
                                profile_page.locator("textarea#custom-message").fill(message[:300])
                                d(1, 2)
                                if not safe_click(profile_page, "button[aria-label='Send invitation']", timeout=action_wait_ms):
                                    safe_click(profile_page, "button[aria-label='Send now']", timeout=action_wait_ms)
                            else:
                                safe_click(profile_page, "button[aria-label='Send now']", timeout=action_wait_ms)

                            d(2, 3)

                        finally:
                            log.info(f"   Following {name}")
                            try:
                                # Some profiles have multiple follow buttons; prefer the 2nd match.
                                follow_on_profile = first_locator_with_nth_visible(
                                    profile_page, FOLLOW_SELECTORS, nth=1, timeout=quick_wait_ms
                                ) or first_locator_with_nth_visible(profile_page, FOLLOW_SELECTORS, nth=0, timeout=quick_wait_ms)
                                if follow_on_profile:
                                    try:
                                        follow_on_profile.nth(1).click()
                                    except Exception:
                                        follow_on_profile.nth(0).click()
                                    log.info(f"   Followed {name}")
                            except Exception:
                                pass
                            profile_page.close()

                    else:
                        log.info(f"   Already connected to {name} — skipping.")
                        continue

                    log_connection(name, company, profile_url, message)
                    connected += 1
                    total_connected += 1
                    log.info(f"✅ [{connected}/{max_connects}] Connected: {name} @ {company} (total: {total_connected})")
                    d(3, 6)

                except Exception as e:
                    log.debug(f"   Person card error: {e}")
                    continue

            # ── End of page — check if Next exists ────────────────────────────
            if connected >= max_connects:
                break

            if element_exists(page, NEXT_BTN_SEL, timeout=3000):
                log.info(f"   Moving to page {current_page + 1}...")
                current_page += 1
                d(2, 4)
            else:
                log.info(f"   No more pages for '{role_keyword}'.")
                break

        d(5, 10)

    log.info(f"Networking run complete. Total connections sent: {total_connected}")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="LinkedIn Bot — Playwright Edition")
    parser.add_argument(
        "--mode",
        choices=["apply", "connect", "report", "all"],
        default="all",
        help="Bot mode to run",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without visible window",
    )
    args = parser.parse_args()

    init_db()

    if args.mode == "report":
        print_report()
        return

    config = load_config()
    if not config["credentials"]["email"] or not config["credentials"]["password"]:
        log.error("LINKEDIN_EMAIL and LINKEDIN_PASSWORD must be set in .env. Copy .env.example to .env and fill in your credentials.")
        return

    with sync_playwright() as playwright:
        browser, context = create_browser(playwright, headless=args.headless)
        page = context.new_page()

        try:
            linkedin_login(page, config["credentials"]["email"], config["credentials"]["password"])

            if args.mode in ("apply", "all"):
                apply_to_jobs(page, config)
                human_delay(5, 10)

            if args.mode in ("connect", "all"):
                search_hr_recruiters(page, config)

            print_report()

        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
        except Exception as e:
            log.error(f"Fatal error: {e}", exc_info=True)
            SCREENSHOTS_DIR.mkdir(exist_ok=True)
            error_screenshot = SCREENSHOTS_DIR / "error.png"
            page.screenshot(path=str(error_screenshot))
            log.info(f"Screenshot saved → {error_screenshot}")
        finally:
            context.close()
            browser.close()
            log.info("Browser closed. Done.")


if __name__ == "__main__":
    main()