# Scrape.py
# pip install playwright psycopg[binary] python-dotenv
# playwright install chromium

import asyncio
import os
import re
from datetime import datetime
from urllib.parse import urljoin

from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
import psycopg

BASE = "https://viesiejipirkimai.lt"
START_URL = f"{BASE}/epps/quickSearchAction.do?searchType=noticeFTS&latest=true"

# ---------- helpers

def parse_publish_date(text: str) -> str | None:
    """Return YYYY-MM-DD from the two common formats seen on the site."""
    s = " ".join((text or "").split())

    # 1) dd/mm/yyyy HH:MM:SS
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", s)
    if m:
        d, mth, y = map(int, m.groups())
        return f"{y:04d}-{mth:02d}-{d:02d}"

    # 2) Thu Oct 16 21:00:00 EEST 2025  (strip TZ token)
    s2 = re.sub(r"\b[A-Z]{2,5}\b", "", s)  # drop EET/EEST/etc
    for fmt in ("%a %b %d %H:%M:%S %Y", "%b %d %Y"):
        try:
            dt = datetime.strptime(" ".join(s2.split()), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


async def select_rows_per_page(page, value: str = "100") -> bool:
    """Try several selectors to change 'rows per page' to the given value."""
    selectors_try = [
        'select[id="T01_ps"]',
        'select',
    ]
    for sel in selectors_try:
        loc = page.locator(sel).first
        if await loc.count():
            try:
                await loc.select_option(value, timeout=3000)
                return True
            except Exception:
                try:
                    await loc.select_option(label=value)
                    return True
                except Exception:
                    continue
    return False


async def find_results_table(page):
    """Return a locator for the visible results table (LT or EN header)."""
    candidates = [
        'table:visible:has(th:has-text("Pranešimo ID"))',  # Lithuanian UI
        'table:visible:has(th:has-text("Notice ID"))',     # English UI
    ]
    for sel in candidates:
        table = page.locator(sel).first
        if await table.count():
            return table
    return page.locator("table:visible").first


# ---------- main scraping routine

async def scrape_latest_100() -> list[dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="lt-LT")
        page = await ctx.new_page()

        await page.goto(START_URL, wait_until="domcontentloaded")
        # Switch to 100 rows per page in the UI
        changed = await select_rows_per_page(page, "100")
        if changed:
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except PWTimeout:
                pass

        # Find the results table and ensure rows are present
        table = await find_results_table(page)
        await table.wait_for(state="visible", timeout=15000)
        tbody_rows = table.locator("tbody > tr:visible")
        await tbody_rows.first.wait_for(timeout=15000)

        # Freeze to element handles; use query_selector* (works on all versions)
        row_handles = await tbody_rows.element_handles()

        data: list[dict] = []
        for row in row_handles:
            cells = await row.query_selector_all("td")
            if len(cells) < 6:
                continue

            # --- ID + URL from column 2 (index 1) ---
            a = await cells[1].query_selector("a")
            if a:
                notice_id = ((await a.text_content()) or "").strip()
                href = await a.get_attribute("href")
                notice_url = urljoin(BASE, href) if href else "Not Listed"
            else:
                # no link -> fall back to plain text in the same cell
                notice_id = ((await cells[1].text_content()) or "").strip()
                notice_url = "Not Listed"

            if not notice_id:  # cannot store a row without an ID
                continue

            # other columns
            skelbimo_tipas = ((await cells[2].text_content()) or "").strip()
            title          = ((await cells[3].text_content()) or "").strip()
            buyer_name     = ((await cells[4].text_content()) or "").strip()

            publish_raw   = ((await cells[-1].text_content()) or "").strip()
            publish_date  = parse_publish_date(publish_raw)  # keep even if None, or enforce if you want

            data.append({
                "notice_id": notice_id,
                "title": title,
                "buyer_name": buyer_name,
                "skelbimo_tipas": skelbimo_tipas,
                "publish_date": publish_date,
                "notice_url": notice_url,
            })

        await browser.close()
        return data


# ---------- database upsert

UPSERT_SQL = """
INSERT INTO notices_stage (
    notice_id, title, buyer_name, skelbimo_tipas, publish_date, notice_url
) VALUES (%s,%s,%s,%s,%s,%s)
ON CONFLICT (notice_id) DO UPDATE
SET
    title = EXCLUDED.title,
    buyer_name = EXCLUDED.buyer_name,
    skelbimo_tipas = EXCLUDED.skelbimo_tipas,
    publish_date = EXCLUDED.publish_date,
    notice_url = EXCLUDED.notice_url,
    scraped_at = now();
"""

def upsert_to_db(rows: list[dict]) -> int:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not set in environment/.env")

    if not rows:
        return 0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for n in rows:
                cur.execute(
                    UPSERT_SQL,
                    (
                        n["notice_id"],
                        n["title"],
                        n["buyer_name"],
                        n["skelbimo_tipas"],
                        n["publish_date"],
                        n["notice_url"],
                    ),
                )
        conn.commit()
    return len(rows)


# ---------- entrypoint

if __name__ == "__main__":
    notices = asyncio.run(scrape_latest_100())
    print(f"Scraped rows: {len(notices)}")
    for n in notices[:5]:
        print(n)

    try:
        count = upsert_to_db(notices)
        print(f"✅ Inserted/updated {count} rows into notices_stage.")
    except Exception as e:
        print(f"⚠️ DB step skipped/failed: {e}")
