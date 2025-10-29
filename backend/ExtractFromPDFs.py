# ExtractFromPDFs.py
import os
import re
import io
import sys
import time
import json
import random
import logging
import pathlib
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urljoin

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
import requests
from dotenv import load_dotenv, find_dotenv

# Load .env even if script runs from /backend
load_dotenv(find_dotenv(usecwd=True))

# -------------------------
# Config
# -------------------------
BATCH_LIMIT = int(os.getenv("BATCH_LIMIT", "30"))
REQ_TIMEOUT = int(os.getenv("REQ_TIMEOUT", "25"))
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TEXT_DIR = pathlib.Path(os.getenv("TEXT_DIR", "pdf_text"))
TEXT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# -------------------------
# DB
# -------------------------
def db_connect():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn

SELECT_SQL = """
SELECT notice_id, pdf_urls
FROM public.notices_stage
WHERE (
       buyer_name IS NULL
    OR pirkimo_budas IS NULL
    OR procedura_pagreitinta IS NULL
    OR aprasymas IS NULL
    OR lots IS NULL
    OR viso_sutarciu_verte IS NULL   -- 👈 add this line
)
  AND pdf_urls IS NOT NULL
ORDER BY publish_date DESC NULLS LAST, notice_id;
"""

def get_work(conn, limit: int) -> List[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(SELECT_SQL, (limit,))
        return cur.fetchall()

def db_update_partial(conn, notice_id: str, fields: Dict[str, Any], status: str):
    keys = [k for k, v in fields.items() if v is not None]
    sets, params = [], []
    for k in keys:
        sets.append(f"{k} = %s")
        v = fields[k]
        # wrap JSON-ish values so psycopg2 knows how to send them
        if isinstance(v, (dict, list)) or k in ("lots", "viso_sutarciu_verte"):
            params.append(Json(v))
        else:
            params.append(v)
    sets.append("extraction_status = %s"); params.append(status)
    sets.append("last_extracted_at = NOW()")
    sql = f"UPDATE public.notices_stage SET {', '.join(sets)} WHERE notice_id = %s"
    params.append(notice_id)
    with conn.cursor() as cur:
        cur.execute(sql, params)

# -------------------------
# HTTP
# -------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "lt,lt-LT;q=0.9,en;q=0.8",
})
PDF_EXT_RE = re.compile(r"\.pdf($|\?)", re.IGNORECASE)

def get_url(url: str) -> requests.Response:
    headers = {"Referer": url.split("/epps/")[0] if "/epps/" in url else url}
    resp = SESSION.get(url, timeout=REQ_TIMEOUT, allow_redirects=True, headers=headers)
    resp.raise_for_status()
    return resp

def looks_like_pdf(resp: requests.Response, head: bytes) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    cdisp = (resp.headers.get("Content-Disposition") or "")
    filename = ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cdisp, re.IGNORECASE)
    if m:
        filename = m.group(1)
    return ("pdf" in ctype) or (filename and filename.lower().endswith(".pdf")) or head.startswith(b"%PDF-")

def fetch_pdf_bytes(url: str) -> Tuple[Optional[bytes], Optional[str]]:
    try:
        r = get_url(url)
    except Exception as e:
        logging.warning("Initial GET failed: %s (%r)", url, e)
        return None, None

    head = r.content[:8] if r.content else b""
    if looks_like_pdf(r, head):
        return r.content, r.url

    ctype = (r.headers.get("Content-Type") or "").lower()
    if "html" in ctype:
        html = r.text or ""
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
        for h in hrefs:
            if PDF_EXT_RE.search(h):
                pdf_url = urljoin(r.url, h)
                try:
                    r2 = get_url(pdf_url)
                except Exception as e:
                    logging.warning("Follow-up .pdf GET failed: %s (%r)", pdf_url, e)
                    continue
                head2 = r2.content[:8] if r2.content else b""
                if looks_like_pdf(r2, head2):
                    return r2.content, r2.url
    return None, None

# -------------------------
# TEXT EXTRACTION
# -------------------------
def extract_text_pymupdf(data: bytes) -> Optional[str]:
    try:
        import fitz
        out = []
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                out.append(page.get_text("text") or "")
        return "\n".join(out).strip()
    except Exception:
        return None

def extract_text_pdfplumber(data: bytes) -> Optional[str]:
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out).strip()
    except Exception:
        return None

def extract_text_pypdf2(data: bytes) -> Optional[str]:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        out = []
        for p in reader.pages:
            out.append(p.extract_text() or "")
        return "\n".join(out).strip()
    except Exception:
        return None

def extract_text_from_pdf(data: bytes) -> Tuple[str, str]:
    for fn, name in [
        (extract_text_pymupdf, "PyMuPDF"),
        (extract_text_pdfplumber, "pdfplumber"),
        (extract_text_pypdf2, "PyPDF2"),
    ]:
        txt = fn(data)
        if txt and txt.strip():
            return txt, name
    return "", "none"

# -------------------------
# NORMALIZATION & HELPERS
# -------------------------
ZERO_WIDTH = re.compile(r"[\u200B-\u200D\uFEFF]")
UNICODE_DASHES = re.compile(r"[\u00AD\u2010\u2011\u2012\u2013\u2014\u2212]")
WS = re.compile(r"[ \t]+")

def normalize_pdf_text(s: str) -> str:
    if not s:
        return ""
    # normalize whitespace variants
    s = s.replace("\xa0", " ")        # NBSP
    s = s.replace("\u202f", " ")      # NARROW NO-BREAK SPACE
    s = s.replace("\u2007", " ")      # FIGURE SPACE
    # existing rules
    s = ZERO_WIDTH.sub("", s)
    s = UNICODE_DASHES.sub("-", s)
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{2,}", "\n", s)
    return s


def norm_one_line(s: str) -> str:
    s = s.replace("\xa0", " ").replace("\r", " ")
    s = re.sub(r"\s*\n\s*", " ", s)
    s = WS.sub(" ", s).strip()
    return s

def parse_money(s: str) -> Tuple[Optional[float], Optional[str]]:
    if not s:
        return None, None
    cur = "EUR" if re.search(r"\b(EUR|EURO|Eur|€)\b", s, re.IGNORECASE) else None
    num = re.sub(r"[^\d,\. ]", "", s).replace(" ", "")
    if num.count(",") == 1 and num.count(".") == 0:
        num = num.replace(",", ".")
    try:
        return float(num), cur
    except Exception:
        return None, cur

def parse_date_lt(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", s)
    if m:
        d, M, y = m.groups()
        return f"{y}-{M}-{d}"
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        return m.group(0)
    return None

def find_section(text: str, start_pat: str, end_pat: str) -> str:
    ms = re.search(start_pat, text, re.IGNORECASE)
    if not ms:
        return ""
    start = ms.start()
    me = re.search(end_pat, text[ms.end():], re.IGNORECASE)
    if me:
        end = ms.end() + me.start()
        return text[start:end]
    return text[start:]

# -------------------------
# BASIC FIELD EXTRACTORS
# -------------------------
def extract_buyer(text: str) -> Optional[str]:
    m = re.search(r"Oficialus pavadinimas:\s*(.+)", text, re.IGNORECASE)
    if m:
        return norm_one_line(m.group(1))
    return None

def extract_procedure(text: str) -> Tuple[Optional[str], Optional[bool]]:
    budas = None
    pagreitinta = None
    mb = re.search(r"Pirkimo būdas:\s*(.+)", text, re.IGNORECASE)
    if mb:
        budas = norm_one_line(mb.group(1))
    mp = re.search(r"Procedūra pagreitinta:\s*(.+)", text, re.IGNORECASE)
    if mp:
        pagreitinta = mp.group(1).strip().lower().startswith("taip")
    return budas, pagreitinta

def extract_aprasymas(text: str) -> Optional[str]:
    m = re.search(r"\bAprašymas:\s*(.+)", text, re.IGNORECASE)
    if m:
        return norm_one_line(m.group(1))
    return None

def extract_viso_sutarciu_verte(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract 'Visų šiame pranešime suteiktų sutarčių vertė: ... Euro'
    Robust to line breaks, thin spaces, and punctuation variations.
    """
    # 1) Find the marker (allow for diacritics + optional punctuation)
    marker = re.search(
        r"(?:Vis[ųu]\s+šiame\s+pranešime\s+suteikt[ųu]\s+sutar[čc]i[ųu]\s+vert[ėe])\s*[:\-]?",
        text, re.IGNORECASE
    )
    if not marker:
        return None

    # 2) Look ahead a short window after the marker; collapse whitespace
    window = text[marker.end(): marker.end() + 200]
    window = norm_one_line(window)  # turns newlines/tabs into single spaces

    # 3) Direct regex for the numeric chunk (+ optional currency)
    #    Accepts digits, spaces, thin spaces, commas, dots; currency optional.
    mnum = re.search(
        r"([0-9][0-9 \u00A0\u202F\u2007\.,]*[0-9](?:[.,][0-9]{1,2})?)\s*(?:EUR|Euro|€)?",
        window,
        re.IGNORECASE,
    )
    if not mnum:
        return None

    raw = mnum.group(1)

    # 4) Normalize number and parse
    #    (parse_money already handles comma decimal, but we pass a cleaned string)
    amount, currency = parse_money(raw)
    if amount is None:
        return None
    if not currency and re.search(r"\b(EUR|Euro|€)\b", window, re.IGNORECASE):
        currency = "EUR"

    return {"amount": amount, "currency": currency}


# -------------------------
# LOTS PARSER (two-pass)
# -------------------------
LOT_HEADER = re.compile(r"\bLOT[-\s]?0*(\d+)\b", re.IGNORECASE)

def extract_lots(text: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Pass 1 (Section 5: 'Pirkimo dalis'): lot metadata (title, description, cpv, place, etc.).
    Pass 2 (Section 6: 'Rezultatai'): winners/status/reason/stats per lot.
    Output: dict keyed by 'LOT-####' where each value is a merged LT-named object.
    """
    # Section 5 ends at Section 6; Section 6 ends at Section 7/8 or 'Skelbimo informacija'
    sec5 = find_section(text, r"\n5\s+Pirkimo\s+dalis", r"\n6\s+Rezultatai")
    sec6 = find_section(text, r"\n6\s+Rezultatai", r"\n(?:7|8)\s+|Skelbimo\s+informacija|$\Z")

    lots_map: Dict[str, Dict[str, Any]] = {}

    def blank_lot() -> Dict[str, Any]:
        return {
            "Pavadinimas": "",
            "Aprašymas": "",
            "Sutarties objektas": "",
            "Pagrindinis klasifikacijos kodas (cpv)": "",
            "NUTS": "",
            "Šalis": "",
            "Galiojimas (mėn.)": None,
            "Strateginis tikslas": "",
            "ŽVP: kriterijai": "",
            "Skyrimo kriterijai": {"Rūšis": "", "Aprašymas": ""},
            "Info_winner": [],
            # NEW structured result block:
            "Rezultatas": {
                "Būsena": None,   # "neapdovanota" when no winner
                "Žinutė": None,   # full 'Nepasirinktas…' line
                "Priežastis": None,
                "Statistika": {"Gautų pasiūlymų ar dalyvavimo prašymų skaičius": None}
            },
            "Rezultatas_tekstas": None,  # combined single string (optional convenience)

            # keep old fields for compatibility with existing consumers
            "Statistika": {"Gautų pasiūlymų ar dalyvavimo prašymų skaičius": None},
            "Neapdovanota": False,
            "Neapdovanota priežastis": ""
        }


    # ---- PASS 1: Section 5 - metadata ----
    if sec5:
        # Find each "5.1 Techninės ID dalies: LOT-####" block
        for m in re.finditer(r"5\.1\s+Techninės\s+ID\s+dalies:\s*(LOT[-\s]?0*\d+)", sec5, re.IGNORECASE):
            lot_token = m.group(1)
            lot_num_m = LOT_HEADER.search(lot_token)
            if not lot_num_m:
                continue
            lot_id = f"LOT-{int(lot_num_m.group(1)):04d}"

            start = m.end()
            nm = re.search(r"5\.1\s+Techninės\s+ID\s+dalies:\s*LOT", sec5[start:], re.IGNORECASE)
            end = start + nm.start() if nm else len(sec5)
            block = sec5[start:end]

            lot = lots_map.setdefault(lot_id, blank_lot())

            # Pull fields from Section 5
            val = lambda pat: norm_one_line(re.search(pat, block, re.IGNORECASE).group(1)) \
                              if re.search(pat, block, re.IGNORECASE) else None

            pavadinimas = val(r"\bPavadinimas:\s*(.+)")
            aprasymas = val(r"\bAprašymas:\s*(.+)")
            sut_obj = val(r"Sutarties\s+objektas:\s*(.+)")
            cpv = val(r"Pagrindinis\s+klasifikacijos\s+kodas\s*\(cpv\)\s*:\s*([0-9]+.*)")
            nuts = val(r"NUTS\):\s*(.+)")
            salis = val(r"Šalis:\s*(.+)")
            galiojimas = val(r"Galiojimas:\s*(\d+)\s+Mėnuo")
            strateginis = val(r"Strateginio\s+viešojo\s+pirkimo\s+tikslas:\s*(.+)")
            zvp_krit = val(r"Žaliasis\s+viešasis\s+pirkimas:\s*kriterijai:\s*(.+)")
            sk_rusis = val(r"Skyrimo\s+kriterijai[\s\S]*?Rūšis:\s*(.+)")
            sk_aprasymas = val(r"Skyrimo\s+kriterijai[\s\S]*?Aprašymas:\s*(.+)")

            if pavadinimas is not None: lot["Pavadinimas"] = pavadinimas
            if aprasymas is not None: lot["Aprašymas"] = aprasymas
            if sut_obj is not None: lot["Sutarties objektas"] = sut_obj
            if cpv is not None: lot["Pagrindinis klasifikacijos kodas (cpv)"] = cpv
            if nuts is not None: lot["NUTS"] = nuts
            if salis is not None: lot["Šalis"] = salis
            if galiojimas is not None:
                try: lot["Galiojimas (mėn.)"] = int(galiojimas)
                except Exception: pass
            if strateginis is not None: lot["Strateginis tikslas"] = strateginis
            if zvp_krit is not None: lot["ŽVP: kriterijai"] = zvp_krit
            if sk_rusis is not None or sk_aprasymas is not None:
                lot["Skyrimo kriterijai"]["Rūšis"] = sk_rusis or lot["Skyrimo kriterijai"]["Rūšis"]
                lot["Skyrimo kriterijai"]["Aprašymas"] = sk_aprasymas or lot["Skyrimo kriterijai"]["Aprašymas"]

    # ---- PASS 2: Section 6 - results ----
        # ---- PASS 2: Section 6 - results ----
    if sec6:
        # Each results subsection starts with "pirkimo dalies ID: LOT-xxxx"
        for m in re.finditer(r"pirkimo\s+dalies\s+ID:\s*(LOT[-\s]?0*\d+)", sec6, re.IGNORECASE):
            lot_token = m.group(1)
            lot_num_m = LOT_HEADER.search(lot_token)
            if not lot_num_m:
                continue
            lot_id = f"LOT-{int(lot_num_m.group(1)):04d}"

            start = m.end()
            nm = re.search(r"pirkimo\s+dalies\s+ID:\s*LOT", sec6[start:], re.IGNORECASE)
            end = start + nm.start() if nm else len(sec6)
            block = sec6[start:end]

            lot = lots_map.setdefault(lot_id, blank_lot())

            # ---------- NO-WINNER / RESULT HANDLING ----------
            # full "Nepasirinktas nė vienas laimėtojas..." sentence
            mmsg = re.search(
                r"(Nepasirinktas?\s+n[ėe]\s+vienas\s+laim[ėe]tojas[^\n\r]*)",
                block, re.IGNORECASE)
            if mmsg:
                message = norm_one_line(mmsg.group(1))
                lot["Rezultatas"]["Būsena"] = "neapdovanota"
                lot["Rezultatas"]["Žinutė"] = message
                lot["Neapdovanota"] = True

            # reason line
            mreason = re.search(
                r"Priežastis[, ]*\s*dėl\s+kurios\s+laimėtojas\s+nebuvo\s+pasirinktas:\s*([^\n\r]+)",
                block, re.IGNORECASE)
            if mreason:
                reason = norm_one_line(mreason.group(1))
                lot["Rezultatas"]["Priežastis"] = reason
                lot["Neapdovanota priežastis"] = reason

            # bids/applications count
            mbids = re.search(
                r"Gaut[ųu]\s+pasiūlym[ųu].{0,120}?skaičius\s*:\s*([0-9]+)",
                block, re.IGNORECASE | re.DOTALL)
            if mbids:
                num = int(mbids.group(1))
                lot["Rezultatas"]["Statistika"]["Gautų pasiūlymų ar dalyvavimo prašymų skaičius"] = num
                lot["Statistika"]["Gautų pasiūlymų ar dalyvavimo prašymų skaičius"] = num

            # optional: build a single readable line
            if lot["Rezultatas"]["Žinutė"] or lot["Rezultatas"]["Priežastis"]:
                parts = []
                if lot["Rezultatas"]["Žinutė"]:
                    parts.append(lot["Rezultatas"]["Žinutė"])
                if lot["Rezultatas"]["Priežastis"]:
                    parts.append("Priežastis, dėl kurios laimėtojas nebuvo pasirinktas: " +
                                 lot["Rezultatas"]["Priežastis"])
                lot["Rezultatas_tekstas"] = " ".join(parts)
            # ---------- END RESULT HANDLING ----------

            # Winners (only if not explicitly unawarded)
            if not lot["Neapdovanota"]:
                winner_blocks = re.split(r"\bLaimėtoja(?:s|i)\b\s*:\s*", block, flags=re.IGNORECASE)
                for wb in winner_blocks[1:]:
                    mname = re.search(r"Oficialus\s+pavadinimas:\s*(.+)", wb, re.IGNORECASE)
                    name = norm_one_line(mname.group(1)) if mname else ""

                    mo = re.search(r"Pasiūlymo\s+identifikatorius:\s*([^\n]+)", wb, re.IGNORECASE)
                    offer_id = norm_one_line(mo.group(1)) if mo else ""

                    mv = re.search(r"Pasiūlymo\s+vertė:\s*([^\n]+)", wb, re.IGNORECASE)
                    amount = currency = None
                    if mv:
                        amount, currency = parse_money(mv.group(1))

                    mcd = re.search(r"Sutarties\s+sudarymo\s+data:\s*([^\n]+)", wb, re.IGNORECASE)
                    contract_date = parse_date_lt(mcd.group(1)) if mcd else None

                    lot["Info_winner"].append({
                        "Oficialus pavadinimas": name,
                        "Pasiūlymo identifikatorius": offer_id,
                        "Pasiūlymo vertė (EUR)": amount,
                        "Sutarties sudarymo data": contract_date
                    })


    if not lots_map:
        return None

    return lots_map  # dict keyed by LOT-####

# -------------------------
# MAIN
# -------------------------
def preview(text: str, n: int = 500) -> str:
    snippet = text[:n].replace("\n", " ").replace("\r", " ")
    return snippet + ("..." if len(text) > n else "")

def main():
    conn = db_connect()
    rows = get_work(conn, BATCH_LIMIT)
    if not rows:
        logging.info("No rows need extraction based on current NULL filters.")
        return

    logging.info("Found %d rows to try.", len(rows))
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        notice_id = row["notice_id"]
        url = row["pdf_urls"]
        logging.info("[%d/%d] notice_id=%s", i, len(rows), notice_id)

        try:
            data, final_url = fetch_pdf_bytes(url)
            if not data:
                db_update_partial(conn, notice_id, {}, "download_failed")
                logging.warning("Could not download PDF for %s", notice_id)
                fail += 1
                continue

            text, method = extract_text_from_pdf(data)
            if not text:
                db_update_partial(conn, notice_id, {}, "empty_text")
                logging.warning("Empty text after extraction (method=%s) for %s", method, notice_id)
                fail += 1
                continue

            text = normalize_pdf_text(text)

            # Keep a copy for debugging/iteration
            out_path = TEXT_DIR / f"{notice_id}.txt"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)

            # Extract fields (NULL-on-unknown policy)
            viso_sutarciu_verte = extract_viso_sutarciu_verte(text)
            buyer, (budas, pagreitinta), desc = None, (None, None), None
            try:
                buyer = extract_buyer(text)
                budas, pagreitinta = extract_procedure(text)
                desc = extract_aprasymas(text)
            except Exception:
                # Never fail the whole notice on a single extractor
                pass

            lots = None
            try:
                lots = extract_lots(text)
            except Exception as e:
                logging.warning("extract_lots failed for %s: %r", notice_id, e)

            extracted: Dict[str, Any] = {
                #"buyer_name": buyer if buyer else None,
                "pirkimo_budas": budas if budas else None,
                "procedura_pagreitinta": pagreitinta if pagreitinta is not None else None,
                "aprasymas": desc if desc else None,
                "lots": lots if lots else None,
                "viso_sutarciu_verte": viso_sutarciu_verte if viso_sutarciu_verte else None,
            }

            db_update_partial(conn, notice_id, extracted, status="ok")
            logging.info(
                "OK notice_id=%s | method=%s | from=%s\nPreview: %s",
                notice_id, method, final_url, preview(text, 400)
            )
            ok += 1

        except Exception as e:
            logging.exception("Failed on notice_id=%s: %r", notice_id, e)
            try:
                db_update_partial(conn, notice_id, {}, status="exception")
            except Exception:
                pass
            fail += 1

        time.sleep(random.uniform(0.2, 0.6))

    logging.info("Done. success=%d, failed=%d.", ok, fail)

if __name__ == "__main__":
    main()
