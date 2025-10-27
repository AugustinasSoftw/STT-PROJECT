#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import re
from typing import List, Dict, Optional
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright
from psycopg2 import connect
from psycopg2.extras import execute_batch
from dotenv import load_dotenv, find_dotenv

# ----- load .env that sits next to this file (backend/.env) -----
env_path = find_dotenv(filename=".env", usecwd=True) or str(
    Path(__file__).with_name(".env")
)
load_dotenv(env_path)

DB_DSN = (os.getenv("DB_DSN") or os.getenv("DATABASE_URL") or "").strip()
DB_DSN = DB_DSN.strip().strip('"').strip("'")  # remove accidental wrapping quotes


# --------- CONFIG ---------
SEARCH_URL = "https://www.e-tar.lt/portal/lt/legalActSearch"


# JSF ids contain ":" -> must be escaped in CSS with "\\:"
THEAD_SEL = "thead#contentForm\\:resultsTable_head"
TBODY_SEL = "tbody#contentForm\\:resultsTable_data"
ROW_SEL = f"{TBODY_SEL} tr[role='row']"
CELL_SEL = "td[role='gridcell']"

# --------- SQL ---------
INSERT_SQL = """
    INSERT INTO sprendimai
      (eil_nr, rusis, pavadinimas, istaigos_nr, priemimo_data, isigaliojimo_data, projektai_nuoroda)
    VALUES
      (%(eil_nr)s, %(rusis)s, %(pavadinimas)s, %(istaigos_nr)s, %(priemimo_data)s, %(isigaliojimo_data)s, %(projektai_nuoroda)s)
      ON CONFLICT (istaigos_nr) DO NOTHING
"""


# --------- HELPERS ---------
def clean(s: str) -> str:
    """Collapse whitespace/newlines to single spaces."""
    return re.sub(r"\s+", " ", (s or "").strip())


DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def ensure_unique_constraint(dsn):
    conn = connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'sprendimai_istaigos_nr_key'
                    ) THEN
                        ALTER TABLE sprendimai
                        ADD CONSTRAINT sprendimai_istaigos_nr_key UNIQUE (istaigos_nr);
                    END IF;
                END$$;
            """
            )
    finally:
        conn.close()


def first_iso_date(text: str) -> Optional[str]:
    """
    Return the first YYYY-MM-DD found in text, else None.
    Postgres DATE accepts ISO strings, so we pass that.
    """
    if not text:
        return None
    m = DATE_RE.search(text)
    return m.group(0) if m else None


async def build_header_map(page) -> Dict[str, int]:
    """Read <thead> once and build {header_text: column_index} (skips empty checkbox header)."""
    th_texts = await page.locator(f"{THEAD_SEL} th").all_inner_texts()
    headers = [clean(t) for t in th_texts]
    return {h: i for i, h in enumerate(headers) if h}


async def parse_rows(page, h2i: Dict[str, int]) -> List[Dict]:
    """Parse tbody rows into dicts using header->index mapping. Keys match INSERT_SQL placeholders."""
    rows = page.locator(ROW_SEL)
    count = await rows.count()
    out: List[Dict] = []

    for i in range(count):
        row = rows.nth(i)
        cells = row.locator(CELL_SEL)

        async def col(name: str) -> str:
            idx = h2i[name]
            txt = await cells.nth(idx).inner_text()
            return clean(txt)

        # --- grab strings (await!) ---
        eil_nr_txt = await col("Eil. Nr.")
        rusis = await col("Rūšis")
        pavadinimas = await col("Pavadinimas")
        istaigos_nr = await col("Įstaigos suteiktas Nr.")
        priemimo_raw = await col("Priėmimo data")
        isigaliojimo_raw = await col("Įsigaliojimo data")

        # Normalize/convert types
        eil_nr = int(eil_nr_txt) if eil_nr_txt.isdigit() else None
        priemimo_data = first_iso_date(priemimo_raw)
        isigaliojimo_data = first_iso_date(isigaliojimo_raw)

        # last <a> in the row = projektai/doc link
        links = row.locator("a")
        k = await links.count()
        projektai_nuoroda = await links.nth(k - 1).get_attribute("href") if k else None

        out.append(
            {
                "eil_nr": eil_nr,
                "rusis": rusis,
                "pavadinimas": pavadinimas,
                "istaigos_nr": istaigos_nr,
                "priemimo_data": priemimo_data,  # ISO date or None
                "isigaliojimo_data": isigaliojimo_data,  # ISO date or None
                "projektai_nuoroda": projektai_nuoroda,
            }
        )

    return out


def save_rows(rows: List[Dict], dsn: str) -> int:
    """Batch insert rows into Postgres."""
    if not rows:
        print("No rows to insert.")
        return 0
    conn = connect(dsn)
    try:
        with conn, conn.cursor() as cur:
            execute_batch(cur, INSERT_SQL, rows, page_size=500)
        print(f"Inserted {len(rows)} rows.")
        return len(rows)
    finally:
        conn.close()


# --------- MAIN ---------
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        page = await browser.new_page(
            viewport={
                "width": 1366,
                "height": 768,
            },  # or 1920x1080 if that’s what works
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            color_scheme="light",
            locale="en-US",
            device_scale_factor=1,
        )

        ensure_unique_constraint(DB_DSN)

        # 1) Open page
        await page.goto(SEARCH_URL, wait_until="domcontentloaded")

        # 2) Click the specific "Ieškoti" (there are two; this one is the main button)
        await page.locator("#contentForm\\:searchParamPane\\:searchButton").click()

        # 3) Wait for rows
        await page.wait_for_selector(ROW_SEL)

        # 4) Header map + parse
        h2i = await build_header_map(page)
        required = {
            "Eil. Nr.",
            "Rūšis",
            "Pavadinimas",
            "Įstaigos suteiktas Nr.",
            "Priėmimo data",
            "Įsigaliojimo data",
        }
        missing = required - set(h2i.keys())
        if missing:
            print("Warning: missing headers:", missing)

        records = await parse_rows(page, h2i)

        # (Optional) preview one normalized row
        if records:
            print("Sample row:", records[0])

        # 5) Insert into Postgres
        save_rows(records, DB_DSN)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
