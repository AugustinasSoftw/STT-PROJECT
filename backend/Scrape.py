import os
import re
import json
import csv
import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

# -------------------------------------------------------
# Config
# -------------------------------------------------------

START_URL = (
    "https://viesiejipirkimai.lt/epps/quickSearchAction.do"
    "?searchType=noticeFTS&latest=true"
)

# PAGE LIMIT:
#   - set PAGE_LIMIT > 0 to cap pages (e.g., 4)
#   - set PAGE_LIMIT = 0 (or unset) to scrape ALL pages
PAGE_LIMIT = int(os.getenv("PAGE_LIMIT", "0"))

# If True: we open the detail page (whose URL we now store in pdf_urls)
# and optionally extract .pdf links there (not stored; only for debugging).
EXTRACT_PDFS = False
PDF_CONCURRENCY = 4

# polite delay between pages
PER_REQUEST_WAIT_MS = (600, 1200)  # (min,max) ms

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS notices_stage (
    notice_id      TEXT PRIMARY KEY,
    title          TEXT,
    skelbimo_tipas TEXT,
    publish_date   TIMESTAMP NULL,
    pdf_urls       TEXT NULL
);
"""

# Upsert:
# - Insert new rows
# - On conflict, UPDATE only if at least one column changed (IS DISTINCT FROM)
# - RETURNING tells us whether it was an insert or update
UPSERT_SQL = """
INSERT INTO notices_stage
(notice_id, title, skelbimo_tipas, publish_date, pdf_urls)
VALUES %s
ON CONFLICT (notice_id) DO UPDATE SET
  title          = EXCLUDED.title,
  skelbimo_tipas = EXCLUDED.skelbimo_tipas,
  publish_date   = EXCLUDED.publish_date,
  pdf_urls       = EXCLUDED.pdf_urls
WHERE (EXCLUDED.title          IS DISTINCT FROM notices_stage.title)
   OR (EXCLUDED.skelbimo_tipas IS DISTINCT FROM notices_stage.skelbimo_tipas)
   OR (EXCLUDED.publish_date   IS DISTINCT FROM notices_stage.publish_date)
   OR (EXCLUDED.pdf_urls       IS DISTINCT FROM notices_stage.pdf_urls)
RETURNING notice_id, (xmax = 0) AS inserted, (xmax <> 0) AS updated;
"""

# -------------------------------------------------------
# Utils
# -------------------------------------------------------

def parse_publish_date(text: Optional[str]) -> Optional[datetime]:
    """
    Accepts:
      - '24/10/2025 16:21:16' or '24/10/2025 16:21'
      - '24/10/2025'
      - 'Thu Oct 16 21:00:00 EEST 2025' (drops the TZ token)
    Returns a Python datetime (time=00:00:00 if not present), or None.
    """
    if not text:
        return None

    # normalize whitespace / NBSP
    s = " ".join(text.replace("\xa0", " ").split())

    # 1) dd/mm/yyyy [HH:MM[:SS]]
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?\b", s)
    if m:
        d, mth, y = map(int, m.group(1, 2, 3))
        t = m.group(4) or "00:00:00"
        if len(t) == 5:  # HH:MM -> add seconds
            t += ":00"
        hh, mm, ss = map(int, t.split(":"))
        try:
            return datetime(y, mth, d, hh, mm, ss)
        except ValueError:
            return None

    # 2) Thu Oct 16 21:00:00 EEST 2025 (drop TZ like EET/EEST)
    s2 = re.sub(r"\b[A-Z]{2,5}\b", "", s)  # remove TZ token
    for fmt in ("%a %b %d %H:%M:%S %Y", "%b %d %Y"):
        try:
            dt = datetime.strptime(" ".join(s2.split()), fmt)
            # ensure time component if not present
            if "%H" not in fmt:
                dt = datetime(dt.year, dt.month, dt.day, 0, 0, 0)
            return dt
        except ValueError:
            pass

    return None

def jitter(min_ms: int, max_ms: int) -> int:
    import random
    return random.randint(min_ms, max_ms)

# -------------------------------------------------------
# DB
# -------------------------------------------------------

def db_connect():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    # full connection string, e.g. postgresql://user:pass@host:5432/db?sslmode=require
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    params = conn.get_dsn_parameters()
    print("DB connected:", params.get("dbname"), "@", params.get("host"))
    return conn

def db_prepare(conn):
    with conn.cursor() as cur:
        cur.execute(CREATE_SQL)
    conn.commit()

def db_upsert_rows(conn, rows: List[Dict[str, Any]]):
    """
    Attempts all valid rows. Returns dict with:
    - inserted, updated, unchanged counts
    - ids_inserted, ids_updated, ids_unchanged
    - ids_missing_after_commit (sanity check)
    - ids_attempted
    - skipped_invalid (rows missing notice_id)
    """
    if not rows:
        return {
            "inserted": 0, "updated": 0, "unchanged": 0,
            "ids_inserted": [], "ids_updated": [], "ids_unchanged": [],
            "ids_missing_after_commit": [], "ids_attempted": [],
            "skipped_invalid": []
        }

    # Minimal validation: we cannot insert without a primary key
    valid_rows = []
    skipped_invalid = []
    for r in rows:
        nid = (r.get("notice_id") or "").strip()
        if not nid:
            r["_skip_reason"] = "missing_notice_id"
            skipped_invalid.append(r)
            continue
        valid_rows.append(r)

    if not valid_rows:
        return {
            "inserted": 0, "updated": 0, "unchanged": 0,
            "ids_inserted": [], "ids_updated": [], "ids_unchanged": [],
            "ids_missing_after_commit": [], "ids_attempted": [],
            "skipped_invalid": skipped_invalid
        }

    values = [
        (
            r["notice_id"],
            r["title"],
            r["skelbimo_tipas"],
            r["publish_date"],
            r.get("pdf_urls"),
        )
        for r in valid_rows
    ]
    ids_attempted = [r["notice_id"] for r in valid_rows]

    try:
        with conn.cursor() as cur:
            # INSERT/UPDATE returning only the rows that actually changed something (insert or update)
            execute_values(cur, UPSERT_SQL, values, page_size=200)
            returned = cur.fetchall()  # list of (notice_id, inserted_bool, updated_bool)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    ids_changed = [rid for (rid, _ins, _upd) in returned]
    # unchanged = attempted - changed
    set_attempted = set(ids_attempted)
    set_changed   = set(ids_changed)
    ids_unchanged = sorted(set_attempted - set_changed)

    ids_inserted = [rid for (rid, ins, _upd) in returned if ins]
    ids_updated  = [rid for (rid, ins, upd) in returned if (not ins) and upd]

    # verify all attempted IDs exist after commit (should be all attempted)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT notice_id FROM notices_stage WHERE notice_id = ANY(%s)",
            (ids_attempted,)
        )
        present = {row[0] for row in cur.fetchall()}

    ids_missing_after_commit = sorted(set_attempted - present)

    return {
        "inserted": len(ids_inserted),
        "updated": len(ids_updated),
        "unchanged": len(ids_unchanged),
        "ids_inserted": ids_inserted,
        "ids_updated": ids_updated,
        "ids_unchanged": ids_unchanged,
        "ids_missing_after_commit": ids_missing_after_commit,
        "ids_attempted": ids_attempted,
        "skipped_invalid": skipped_invalid,
    }

# -------------------------------------------------------
# Scraping
# -------------------------------------------------------

async def set_per_page_100(page):
    # Try <select>
    try:
        selects = page.locator("select")
        if await selects.count():
            for i in range(await selects.count()):
                sel = selects.nth(i)
                options = await sel.locator("option").all_text_contents()
                if any(o.strip() == "100" for o in options):
                    await sel.select_option(label="100")
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(0.4)
                    return
    except Exception:
        pass
    # Try a button-based dropdown
    try:
        candidates = [
            page.get_by_role("button", name=re.compile(r"^\s*100\s*$")),
            page.locator("button, [role='button']").filter(has_text=re.compile(r"^\s*100\s*$")),
        ]
        for loc in candidates:
            if await loc.count():
                await loc.first.click()
                opt = page.locator("text=100").first
                if await opt.count():
                    await opt.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(0.4)
                    return
    except Exception:
        pass

async def extract_rows_on_page(page) -> List[Dict[str, Any]]:
    """
    Extract notice rows — pdf_urls now stores what notice_url used to (detail page URL).
    """
    try:
        await page.locator("table tbody tr").first.wait_for(timeout=15000)
    except PWTimeout:
        await asyncio.sleep(1.0)

    rows = await page.eval_on_selector_all(
        "table tbody tr",
        r"""
        (trs) => trs.map(tr => {
          const norm = (s) => (s || '').replace(/\u00a0/g,' ').toLowerCase().replace(/\s+/g,' ').trim();
          const tds  = Array.from(tr.querySelectorAll('td'));

          const byCol = (targets) => {
            const cand = tds.filter(td => td.hasAttribute('data-column'));
            for (const td of cand) {
              const v = norm(td.getAttribute('data-column'));
              for (const tgt of targets) {
                if (v.startsWith(norm(tgt)) || v === norm(tgt)) return td;
              }
            }
            return null;
          };

          const idTd    = byCol(['Pranešimo ID','Notice ID']) || tds[1] || null;
          const typeTd  = byCol(['Pranešimo tipas','Notice type']) || tds[2] || null;
          const titleTd = byCol(['Pranešimo pavadinimas','Notice title']) || tds[3] || null;

          let dateTd = byCol(['Paskelbimo data','Publish date']);
          if (!dateTd) dateTd = tds[tds.length - 1] || null;

          const anchors = Array.from(tr.querySelectorAll('a'));
          // detail page (non-PDF) — this is what used to go to notice_url
          const detailA  = anchors.find(a => !/\.pdf(\?|$)/i.test(a.href)) || anchors[0] || null;

          const notice_id = ((idTd?.textContent) || '').trim();
          const title     = ((titleTd?.textContent) || '').trim();
          const skelbimo_tipas = ((typeTd?.textContent) || '').trim();

          const publish_date_text = ((dateTd?.innerText) || '')
            .replace(/\u00a0/g,' ')
            .replace(/\s+/g,' ')
            .trim();

          const detailUrl = detailA ? detailA.href : null;

          return {
            notice_id,
            title,
            skelbimo_tipas,
            publish_date_text,
            pdf_urls: detailUrl,   // repurposed to store the detail link
            _detail_url: detailUrl // internal helper for EXTRACT_PDFS (optional)
          };
        })
        """
    )

    # Python-side normalization
    for r in rows:
        pub_dt = parse_publish_date(r.get("publish_date_text"))
        r["publish_date"] = pub_dt
        r.pop("publish_date_text", None)

    return rows

async def click_next(page) -> bool:
    # 1) explicit Kitas/Next
    for sel in [
        'a[title="Kitas"]',
        'button[title="Kitas"]',
        "a:has-text('Kitas')",
        "button:has-text('Kitas')",
        "a:has-text('Next')",
        "button:has-text('Next')",
    ]:
        loc = page.locator(sel).first
        if await loc.count():
            if (await loc.get_attribute("disabled")) is not None:
                return False
            if (await loc.get_attribute("aria-disabled")) == "true":
                return False
            if not await loc.is_enabled():
                return False
            try:
                await asyncio.gather(
                    page.wait_for_load_state("domcontentloaded"),
                    loc.click(),
                )
            except PWTimeout:
                return False
            await asyncio.sleep(0.5)
            return True

    # 2) right-arrow next to “Puslapis X” control (best-effort)
    pager_btns = page.locator("button:has-text('Puslapis')")
    if await pager_btns.count():
        pager_right = pager_btns.first.locator("xpath=following-sibling::button[1]")
        if await pager_right.count():
            if not await pager_right.is_enabled():
                return False
            try:
                await asyncio.gather(
                    page.wait_for_load_state("domcontentloaded"),
                    pager_right.click(),
                )
            except PWTimeout:
                return False
            await asyncio.sleep(0.5)
            return True

    # 3) generic › / »
    for sel in ["a:has-text('›')", "button:has-text('›')", "a:has-text('»')", "button:has-text('»')"]:
        loc = page.locator(sel).first
        if await loc.count():
            if not await loc.is_enabled():
                return False
            try:
                await asyncio.gather(
                    page.wait_for_load_state("domcontentloaded"),
                    loc.click(),
                )
            except PWTimeout:
                return False
            await asyncio.sleep(0.5)
            return True

    return False

async def extract_pdf_links(browser_context, url: str) -> List[str]:
    """Extract any .pdf links from a detail page (debug only, not stored)."""
    pdfs: List[str] = []
    if not url:
        return pdfs
    page = await browser_context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        anchors = page.locator("a[href$='.pdf'], a[href*='.pdf?']")
        if await anchors.count():
            hrefs = await anchors.evaluate_all("els => els.map(e => e.href)")
            seen = set()
            for h in hrefs:
                if h and h not in seen:
                    seen.add(h)
                    pdfs.append(h)
    except Exception:
        pass
    finally:
        await page.close()
    return pdfs

# -------------------------------------------------------
# Main
# -------------------------------------------------------

async def main():
    conn = db_connect()
    db_prepare(conn)

    all_rows: List[Dict[str, Any]] = []
    report_pages = []   # per-page insert/update/unchanged stats
    attempt_rows = []   # flat list for CSV: page, notice_id, status
    skipped_all = []    # rows skipped due to missing PK (should be rare)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"),
                viewport={"width": 1366, "height": 900},
            )
            page = await ctx.new_page()
            page.set_default_timeout(15000)
            page.set_default_navigation_timeout(30000)

            await page.goto(START_URL, wait_until="domcontentloaded")

            # cookie banner (best effort)
            try:
                for sel in [
                    "button:has-text('Sutinku')",
                    "button:has-text('Accept')",
                    "button#onetrust-accept-btn-handler",
                ]:
                    btn = page.locator(sel).first
                    if await btn.count():
                        await btn.click()
                        break
            except Exception:
                pass

            await set_per_page_100(page)

            page_idx = 1
            while True:
                print(f"Scraping page {page_idx}…")
                rows = await extract_rows_on_page(page)
                if not rows:
                    print("No rows found; stopping.")
                    break

                # Optional: use the detail link (now in pdf_urls) to collect PDFs for debugging
                if EXTRACT_PDFS:
                    sem = asyncio.Semaphore(PDF_CONCURRENCY)
                    async def fetch_from_detail(r):
                        async with sem:
                            extras = await extract_pdf_links(ctx, r.get("_detail_url") or "")
                            r["__pdfs_found"] = extras  # debug only
                        return r
                    rows = await asyncio.gather(*(fetch_from_detail(r) for r in rows))

                # Strip helper key before DB/backup
                for r in rows:
                    r.pop("_detail_url", None)

                # DB upsert per page (so progress is saved)
                try:
                    stats = db_upsert_rows(conn, rows)
                    # Record per-page stats
                    report_pages.append({
                        "page": page_idx,
                        "inserted": stats["inserted"],
                        "updated": stats["updated"],
                        "unchanged": stats["unchanged"],
                        "ids_missing_after_commit": stats["ids_missing_after_commit"],
                        "skipped_invalid_count": len(stats["skipped_invalid"]),
                    })
                    skipped_all.extend(stats["skipped_invalid"])

                    # Build a flat attempt log for CSV
                    set_ins  = set(stats["ids_inserted"])
                    set_upd  = set(stats["ids_updated"])
                    set_unch = set(stats["ids_unchanged"])
                    set_miss = set(stats["ids_missing_after_commit"])
                    for nid in stats["ids_attempted"]:
                        if nid in set_ins:
                            status = "inserted"
                        elif nid in set_upd:
                            status = "updated"
                        elif nid in set_unch:
                            status = "unchanged"
                        elif nid in set_miss:
                            status = "missing_after_commit"
                        else:
                            status = "unknown"  # shouldn’t happen
                        attempt_rows.append({"page": page_idx, "notice_id": nid, "status": status})

                    print(
                        f"DB page {page_idx} — inserted={stats['inserted']}, "
                        f"updated={stats['updated']}, unchanged={stats['unchanged']}, "
                        f"missing_after_commit={len(stats['ids_missing_after_commit'])}, "
                        f"skipped_invalid={len(stats['skipped_invalid'])}"
                    )
                except Exception as e:
                    print(f"DB UPSERT FAILED on page {page_idx}: {repr(e)}")

                all_rows.extend(rows)

                # page cap (only applies if PAGE_LIMIT > 0)
                if PAGE_LIMIT > 0 and page_idx >= PAGE_LIMIT:
                    print(f"Reached PAGE_LIMIT={PAGE_LIMIT}. Stopping.")
                    break

                moved = await click_next(page)
                if not moved:
                    print("Reached last page.")
                    break

                page_idx += 1
                await asyncio.sleep(jitter(*PER_REQUEST_WAIT_MS) / 1000.0)

            await ctx.close()
            await browser.close()

    finally:
        # always keep a local backup for verification
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open("notices.json", "w", encoding="utf-8") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=2, default=json_serial)
        print(f"Saved JSON backup with {len(all_rows)} rows.")

        # Summarize all pages
        tot_inserted  = sum(p["inserted"] for p in report_pages)
        tot_updated   = sum(p["updated"] for p in report_pages)
        tot_unchanged = sum(p["unchanged"] for p in report_pages)
        tot_missing   = sum(len(p.get("ids_missing_after_commit", [])) for p in report_pages)

        run_report = {
            "total_pages": len(report_pages),
            "inserted": tot_inserted,
            "updated": tot_updated,
            "unchanged": tot_unchanged,
            "missing_after_commit": tot_missing,
            "pages": report_pages,
            "skipped_invalid_total": len(skipped_all),
        }
        with open("insert_report.json", "w", encoding="utf-8") as f:
            json.dump(run_report, f, ensure_ascii=False, indent=2)
        print(
            f"Wrote insert_report.json (inserted={tot_inserted}, updated={tot_updated}, "
            f"unchanged={tot_unchanged}, missing={tot_missing}, skipped_invalid={len(skipped_all)})"
        )

        # Flat CSV for easy eyeballing / spreadsheet filtering
        try:
            with open("attempts_vs_db.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["page", "notice_id", "status"])
                w.writeheader()
                w.writerows(attempt_rows)
            print("Wrote attempts_vs_db.csv with per-row statuses.")
        except Exception as _e:
            print(f"Could not write attempts_vs_db.csv: {repr(_e)}")

        # Save any skipped-invalid rows (missing PK)
        if skipped_all:
            with open("skipped_invalid.json", "w", encoding="utf-8") as f:
                json.dump(skipped_all, f, ensure_ascii=False, indent=2, default=json_serial)
            print(f"Wrote skipped_invalid.json — {len(skipped_all)} rows with missing notice_id")

        try:
            conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())
