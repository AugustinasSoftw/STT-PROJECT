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
import unicodedata

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
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
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
    sets.append("extraction_status = %s")
    params.append(status)
    sets.append("last_extracted_at = NOW()")
    sql = f"UPDATE public.notices_stage SET {', '.join(sets)} WHERE notice_id = %s"
    params.append(notice_id)
    with conn.cursor() as cur:
        cur.execute(sql, params)


# -------------------------
# HTTP
# -------------------------
SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "lt,lt-LT;q=0.9,en;q=0.8",
    }
)
PDF_EXT_RE = re.compile(r"\.pdf($|\?)", re.IGNORECASE)


def get_url(url: str) -> requests.Response:
    headers = {"Referer": url.split("/epps/")[0] if "/epps/" in url else url}
    resp = SESSION.get(url, timeout=REQ_TIMEOUT, allow_redirects=True, headers=headers)
    resp.raise_for_status()
    return resp


def looks_like_pdf(resp: requests.Response, head: bytes) -> bool:
    ctype = (resp.headers.get("Content-Type") or "").lower()
    cdisp = resp.headers.get("Content-Disposition") or ""
    filename = ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cdisp, re.IGNORECASE)
    if m:
        filename = m.group(1)
    return (
        ("pdf" in ctype)
        or (filename and filename.lower().endswith(".pdf"))
        or head.startswith(b"%PDF-")
    )


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
                out.append(page.get_text("text") or "")  # type:ignore
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
    s = s.replace("\xa0", " ")  # NBSP
    s = s.replace("\u202f", " ")  # Narrow NBSP
    s = s.replace("\u2007", " ")  # Figure space

    # remove zero-widths & normalize dashes
    s = ZERO_WIDTH.sub("", s)
    s = UNICODE_DASHES.sub("-", s)

    # unify newlines
    s = s.replace("\r", "\n")

    # remove ANY URLs (some notices embed raw https://ted... in the middle of fields)
    s = re.sub(r"https?://\S+", "", s, flags=re.IGNORECASE)

    # also remove page counters if present
    s = re.sub(r"\bPage\s+\d+/\d+\b", "", s, flags=re.IGNORECASE)

    # collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
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
    # DD.MM.YYYY
    m = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", s)
    if m:
        d, M, y = m.groups()
        return f"{y}-{M}-{d}"
    # DD/MM/YYYY
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", s)
    if m:
        d, M, y = m.groups()
        return f"{y}-{M}-{d}"
    # YYYY.MM.DD
    m = re.search(r"\b(\d{4})\.(\d{2})\.(\d{2})\b", s)
    if m:
        y, M, d = m.groups()
        return f"{y}-{M}-{d}"
    # ISO
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", s)
    if m:
        return m.group(0)
    return None


def find_section(text: str, start_pat: str, end_pat: str) -> str:
    ms = re.search(start_pat, text, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    if not ms:
        return ""
    me = re.search(end_pat, text[ms.end() :], re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return text[ms.start() : ms.end() + me.start()] if me else text[ms.start() :]


# -------------------------
# BASIC FIELD EXTRACTORS
# -------------------------
def extract_buyer(text: str) -> Optional[str]:
    sec1 = find_section(text, r"\n1\s+Pirkėjas", r"(?:\n2\s+Procedūra|\Z)")
    if not sec1:
        return None
    m = re.search(r"Oficialus pavadinimas:\s*(.+)", sec1, re.IGNORECASE)
    return norm_one_line(m.group(1)) if m else None


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
        text,
        re.IGNORECASE,
    )
    if not marker:
        return None

    # 2) Look ahead a short window after the marker; collapse whitespace
    window = text[marker.end() : marker.end() + 200]
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


def _strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _norm(s: str) -> str:
    s = _strip_diacritics(s or "")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _label_to_key(label_norm: str) -> str | None:
    # Route many phrasings to stable keys (order matters)
    if label_norm.startswith("rusis"):
        return "Rūšis"
    if label_norm.startswith("pavadinimas"):
        return "Pavadinimas"
    if label_norm.startswith("aprasymas"):
        return "Aprašymas"
    if label_norm.startswith("kategorija"):
        # covers: "kategorija skyrimo kriterijaus slenkstis/svoris"
        return "Kategorija_eilutė"
    if label_norm.startswith("naudotino metodo aprasymas"):
        return "Metodas_aprašymas"
    if label_norm.startswith("pagrindimas"):
        return "Pagrindimas"
    # leave weight for a dedicated detector below
    return None


def _extract_weight_from_block(txt: str) -> int | None:
    """
    Find the numeric weight even with phrasing variations:
    - "Skyrimo kriterijus: skaičius: 85"
    - "... svoris ... 15 %"
    - OCR case: number is at end of the long 'Naudotino metodo aprašymas...' line
    - plain 'skaičius: 100'
    """
    # Priority 1: canonical phrasing
    m = re.search(
        r"Skyrimo\s+kriterijus[^\n:]*:\s*(?:skaičius\s*:)?\s*(\d+)", txt, re.IGNORECASE
    )
    if m:
        return int(m.group(1))

    # Priority 2: any line mentioning svoris/procent and having a number
    for ln in txt.splitlines():
        ln_norm = _norm(ln)
        if any(k in ln_norm for k in ("svoris", "procent", "skaicius")):
            m2 = re.search(r"(\d{1,3})", ln)
            if m2:
                return int(m2.group(1))

    # Priority 3: last integer in the block (fallback)
    ints = re.findall(r"(\d{1,3})", txt)
    if ints:
        return int(ints[-1])

    return None


def parse_criteria_section(lot_block: str) -> tuple[list[dict], dict]:
    """
    Robust parser for '5.1.10 Skyrimo kriterijai'.
    Returns:
      - criteria_list: list of objects with fields (Rūšis, Pavadinimas, Aprašymas,
        Kategorija_eilutė, Svoris, Metodas_aprašymas, Pagrindimas) when present.
      - summary_dict: {"Kaina_%": int, "Kokybė_%": int} if types are mapped.
    """
    # 1) Isolate the criteria section of this LOT
    sec = re.search(
        r"5\.1\.10\s+Skyrimo\s+kriterijai(.*?)(?=\n5\.1\.(?:11|12|13|14|15|16|\d)|\n5\.2|\n6\b|\Z)",
        lot_block,
        re.IGNORECASE | re.DOTALL,
    )
    if not sec:
        return [], {}

    crit_text = sec.group(1)

    # 2) Split into 'Kriterijus:' blocks (allow blank lines after the label)
    parts = re.split(r"\bKriterijus\s*:\s*(?:\n+)?", crit_text, flags=re.IGNORECASE)
    parts = [p for p in parts if p.strip()]
    if not parts:
        # Some notices show a single unlabelled criteria set; fall back to one block
        parts = [crit_text]

    criteria: list[dict] = []
    summary: dict = {}

    for blk in parts:
        item: dict = {}

        # Line-by-line "Label: Value" extraction with tolerant mapping
        for raw_line in blk.splitlines():
            line = raw_line.strip()
            if not line or ":" not in line:
                continue
            label, value = line.split(":", 1)
            key = _label_to_key(_norm(label))
            if key:
                v = re.sub(r"\s+", " ", value).strip()
                if v:
                    item[key] = v

        # Always try to extract Svoris from the whole block (covers many variants)
        weight = _extract_weight_from_block(blk)
        if weight is not None:
            item["Svoris"] = weight

        # Build summary by type (even if weight == 0)
        rusis_norm = _norm(item.get("Rūšis", ""))
        if "Svoris" in item:
            if "kaina" in rusis_norm:
                summary["Kaina_%"] = item["Svoris"]
            elif "kokyb" in rusis_norm:
                summary["Kokybė_%"] = item["Svoris"]

        # Prune empty keys and keep if anything parsed
        item = {k: v for k, v in item.items() if v is not None and v != ""}
        if item:
            criteria.append(item)

    return criteria, summary


def parse_bendra_informacija(lot_block: str) -> dict:
    """
    Parse '5.1.6 Bendra informacija' for a lot block.
    Returns booleans and the first meaningful line, even if the 5.1.6 header is missing.
    """
    # Try to isolate the section first
    sec_m = re.search(
        r"5\.1\.6\s+Bendra\s+informacija(.*?)(?=\n5\.1\.(?:7|8|9|10|11|12|13|14|15|16)|\n5\.2|\n6\b|\Z)",
        lot_block,
        re.IGNORECASE | re.DOTALL,
    )
    t = sec_m.group(1) if sec_m else lot_block  # fallback: search the whole lot block

    # First meaningful line inside the section (if we found it)
    first_line = None
    if sec_m:
        for ln in t.splitlines():
            ln = ln.strip()
            if ln:
                first_line = ln
                break

    # ES funds
    es_funds = None
    if re.search(r"\bIš\s+ES\s+fondų\s+nefinansuojamas\b", t, re.IGNORECASE):
        es_funds = False
    elif re.search(r"finansuojam[asė]\s+iš\s+ES\s+fond", t, re.IGNORECASE):
        es_funds = True

    # SVP
    svp = None
    m = re.search(
        r"Pirkimui\s+taikoma\s+Sutartis\s+dėl\s+viešųjų\s+pirkimų\s*\(SVP\)\s*:\s*(taip|ne)",
        t,
        re.IGNORECASE,
    )
    if m:
        svp = m.group(1).strip().lower() == "taip"

    return {
        "ES_fondai": es_funds,
        "SVP_taikoma": svp,
        "pirma_eilute": first_line,
        "section_found": bool(sec_m),
    }


def _merge_orphan_winner_items(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for it in items:
        has_identity = any(
            it.get(k)
            for k in (
                "Oficialus pavadinimas",
                "Pasiūlymo identifikatorius",
                "Sutarties identifikatorius",
                "Pasiūlymo vertė (EUR)",
            )
        )
        has_dates = any(
            k in it
            for k in (
                "Laimėtojo pasirinkimo data",
                "Sutarties sudarymo data",
                "Sutarties sudarymo datos",
            )
        )
        is_orphan = (not has_identity) and has_dates

        if is_orphan and merged:
            for k, v in it.items():
                if v is not None and k not in merged[-1]:
                    merged[-1][k] = v
        else:
            merged.append(it)
    return merged


def parse_strateginis_vp(lot_block: str) -> dict:
    """
    Parse 5.1.7 Strateginis viešasis pirkimas.
    Returns dict with keys: tikslas, aprasymas, metodas, zvp_kriterijai (any may be None).
    """
    sec = re.search(
        r"5\.\s*1\.\s*7\s+Strateginis\s+viešasis\s+pirkimas(.*?)(?=\n5\.\s*1\.\s*(?:8|9|10|11|12|13|14|15|16|\d)|\n5\.\s*2|\n6\b|\Z)",
        lot_block,
        re.IGNORECASE | re.DOTALL,
    )
    if not sec:
        return {
            "tikslas": None,
            "aprasymas": None,
            "metodas": None,
            "zvp_kriterijai": None,
        }

    t = sec.group(1)

    def grab_line(pat: str):
        m = re.search(pat, t, re.IGNORECASE)
        return m.group(1).strip() if m else None

    # Stop when another labeled field/section begins
    STOP = (
        r"(?=\n(?:Poveikio\s+aplinkai\s+mažinimo\s+metodas\s*:|"
        r"Žaliasis\s+viešasis\s+pirkimas\s*:\s*kriterijai\s*:|"
        r"Kriterijus\s*:|5\.\s*1\.|5\.\s*2|6\b|$))"
    )

    # 1) Try explicit label
    apr = None
    m_apr = re.search(r"Aprašymas\s*:\s*(.+?)" + STOP, t, re.IGNORECASE | re.DOTALL)
    if m_apr:
        apr = re.sub(r"\s*\n\s*", " ", m_apr.group(1))
        apr = re.sub(r"[ \t]+", " ", apr).strip()

    # 2) Fallback: paragraph after 'tikslas:' up to next labeled field
    if not apr:
        m_after_goal = re.search(
            r"Strateginio\s+viešojo\s+pirkimo\s+tikslas\s*:\s*[^\n]+\n(.+?)" + STOP,
            t,
            re.IGNORECASE | re.DOTALL,
        )
        if m_after_goal:
            apr = re.sub(r"\s*\n\s*", " ", m_after_goal.group(1))
            apr = re.sub(r"[ \t]+", " ", apr).strip()

    # 3) Fallback: first meaningful paragraph inside the section
    if not apr:
        for para in re.split(r"\n\s*\n", t.strip()):
            para = re.sub(r"\s*\n\s*", " ", para).strip()
            if para and not re.match(
                r"^(Poveikio|Žaliasis|Kriterijus)\b", para, re.IGNORECASE
            ):
                apr = para
                break

    return {
        "tikslas": grab_line(
            r"Strateginio\s+viešojo\s+pirkimo\s+tikslas\s*:\s*([^\n]+)"
        ),
        "aprasymas": apr,
        "metodas": grab_line(
            r"Poveikio\s+aplinkai\s+mažinimo\s+metodas\s*:\s*([^\n]+)"
        ),
        "zvp_kriterijai": grab_line(
            r"Žaliasis\s+viešasis\s+pirkimas\s*:\s*kriterijai\s*:\s*([^\n]+)"
        ),
    }


def _bool_taip_ne(s: str) -> Optional[bool]:
    if not s:
        return None
    s = s.strip().lower()
    if s.startswith("taip"):
        return True
    if s.startswith("ne"):
        return False
    return None


def _parse_percent(s: str) -> Optional[float]:
    if not s:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m:
        return None
    val = m.group(1).replace(",", ".")
    try:
        return float(val)
    except Exception:
        return None


def _canon_label(s: str) -> str:
    import unicodedata

    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def parse_winner_block(wb: str) -> dict:
    """
    Parse a single 'Laimėtojas' block, including Subranga details.
    """
    item: dict = {}

    # Basic winner fields
    mname = re.search(r"Oficialus\s+pavadinimas:\s*(.+)", wb, re.IGNORECASE)
    if mname:
        item["Oficialus pavadinimas"] = norm_one_line(mname.group(1))

    mo = re.search(r"Pasiūlymo\s+identifikatorius:\s*([^\n]+)", wb, re.IGNORECASE)
    if mo:
        item["Pasiūlymo identifikatorius"] = norm_one_line(mo.group(1))

    mv = re.search(r"Pasiūlymo\s+vertė:\s*([^\n]+)", wb, re.IGNORECASE)
    if mv:
        amt, _cur = parse_money(mv.group(1))
        if amt is not None:
            item["Pasiūlymo vertė (EUR)"] = amt

        # --- Contract identifier (keep as you have) ---
    mcid = re.search(r"Sutarties\s+identifikatorius:\s*([0-9]+)", wb, re.IGNORECASE)
    if mcid:
        item["Sutarties identifikatorius"] = mcid.group(1)

        # --- Dates: grab labeled values first, then fallbacks ---
    dates: list[str] = []

    def _push_date(key: str, raw: str):
        d = parse_date_lt(raw.strip())
        if d:
            item[key] = d
            dates.append(d)

    # 1) Explicit labels (very tolerant; no ^ anchors; accepts ASCII ':' or full-width '：')
    # --- Winner chosen date (exactly like "Sutarties sudarymo data") ---
    pick = re.search(
        r"Data\s*,?\s*kuri[aą]\s+buvo\s+pasirinkt(?:as|i)\s+laim[ėe]toj[au]s?\s*[: \-\u2013]?\s*"
        r"(\d{2}[./-]\d{2}[./-]\d{4}|\d{4}[./-]\d{2}[./-]\d{2})",
        wb,
        re.IGNORECASE,
    )
    if pick:
        _push_date("Laimėtojo pasirinkimo data", pick.group(1))

    sign = re.search(
        r"Sutarties\s+sudarymo\s+data\s*[:：]\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
        wb,
        re.IGNORECASE,
    )
    if sign:
        _push_date("Sutarties sudarymo data", sign.group(1))

    # --- Laimėtojo pasirinkimo data (section-aware, accent/space tolerant) ---

    # 2) one or many "contract signed" dates
    contract_pat = r"Sutarties\s+sudarymo\s+data[^:\n]*[:：-]\s*([0-9./-]+)"
    c_dates = []
    for mcd in re.finditer(contract_pat, wb, re.IGNORECASE):
        d = parse_date_lt(mcd.group(1))
        if d:
            c_dates.append(d)

    if c_dates:
        c_dates = sorted(set(c_dates))
        if len(c_dates) == 1:
            item["Sutarties sudarymo data"] = c_dates[0]
        else:
            item["Sutarties sudarymo datos"] = c_dates

    # 3) Fallback (only if we failed to find any labeled date at all)
    #    Look after the "Informacija apie sutartį" header, then the tail of the block.
    if (
        "Laimėtojo parinkimo data" not in item
        and "Sutarties sudarymo data" not in item
        and "Sutarties sudarymo datos" not in item
    ):

        def _find_all_dates(txt: str) -> list[str]:
            out = []
            for m in re.finditer(r"\b(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b", txt):
                d = parse_date_lt(m.group(1))
                if d:
                    out.append(d)
            return list(dict.fromkeys(out))  # dedupe, keep order

        mis = re.search(r"Informacija\s+apie\s+sutart[įi]\s*[:：]?", wb, re.IGNORECASE)
        tail = wb[mis.end() :] if mis else wb
        dates = _find_all_dates(tail)
        if dates:
            if len(dates) == 1:
                item["Sutarties sudarymo data"] = dates[0]
            else:
                item["Sutarties sudarymo datos"] = dates

    # ---------- Subranga ----------
    msub = re.search(r"\bSubranga\s*:\s*([^\n]+)", wb, re.IGNORECASE)
    sub = _bool_taip_ne(msub.group(1)) if msub else None
    if sub is not None:
        item["Subranga"] = sub

    # Only try detailed fields if Subranga is True (but we still accept if present)
    m_svz = re.search(r"Subrangos\s+vertė\s+žinoma\s*:\s*([^\n]+)", wb, re.IGNORECASE)
    if m_svz:
        item["Subrangos vertė žinoma"] = _bool_taip_ne(m_svz.group(1))

    m_sv = re.search(r"Subrangos\s+vertė\s*:\s*([^\n]+)", wb, re.IGNORECASE)
    if m_sv:
        a, _c = parse_money(m_sv.group(1))
        if a is not None:
            item["Subrangos vertė (EUR)"] = a

    m_spdz = re.search(
        r"Subrangos\s+procentinė\s+dalis\s+žinoma\s*:\s*([^\n]+)", wb, re.IGNORECASE
    )
    if m_spdz:
        item["Subrangos % dalis žinoma"] = _bool_taip_ne(m_spdz.group(1))

    m_spd = re.search(
        r"Subrangos\s+procentinė\s+dalis\s*:\s*([^\n]+)", wb, re.IGNORECASE
    )
    if m_spd:
        p = _parse_percent(m_spd.group(1))
        if p is not None:
            item["Subrangos % dalis"] = p

    # Often a line with names of subcontractors
    # (Use the last 'Aprašymas:' in the winner block to avoid clashing earlier descriptions)
    all_desc = re.findall(r"\bAprašymas\s*:\s*([^\n]+)", wb, re.IGNORECASE)
    if all_desc:
        item["Subrangos aprašymas"] = norm_one_line(all_desc[-1])

    # prune totally empty winner objects
    if not any(item.values()):
        return {}
    return item


# -------------------------
# LOTS PARSER (two-pass)
# -------------------------
LOT_HEADER = re.compile(r"\bLOT[-\s]?0*(\d+)\b", re.IGNORECASE)


def extract_lots(text: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """
    Two-pass LOT parser:
      - Pass 1 over Section 5 ('Pirkimo dalis'): title/description/cpv/NUTS/Šalis/criteria/etc.
      - Pass 2 over Section 6 ('Rezultatai'): winners, non-award messages, stats.
    Returns a dict keyed by 'LOT-####'.
    """
    # Section slicing (robust ends)
    sec5 = find_section(text, r"\n5\s+Pirkimo\s+dalis", r"(?:\n6\s+Rezultatai)")
    sec6 = find_section(
        text, r"\n6\s+Rezultatai", r"(?:\n7\s+|\n8\s+|Skelbimo\s+informacija|\Z)"
    )

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
            "Skyrimo kriterijai": {},  # e.g., {"Kaina_%": 90, "Kokybė_%": 10}
            "Info_winner": [],
            "Rezultatas": {
                "Būsena": None,  # "apdovanota" | "neapdovanota"
                "Žinutė": None,
                "Priežastis": None,
                "Statistika": {"Gautų pasiūlymų ar dalyvavimo prašymų skaičius": None},
            },
            "Rezultatas_tekstas": None,
            "Statistika": {"Gautų pasiūlymų ar dalyvavimo prašymų skaičius": None},
            "Neapdovanota": False,
            "Neapdovanota priežastis": "",
        }

    # =========================
    # PASS 1: Section 5 (meta)
    # =========================
    if sec5:
        for m in re.finditer(
            r"5\.1\s+Techninės\s+ID\s+dalies:\s*(LOT[-\s]?0*\d+)", sec5, re.IGNORECASE
        ):
            lot_token = m.group(1)
            lot_num_m = LOT_HEADER.search(lot_token)
            if not lot_num_m:
                continue
            lot_id = f"LOT-{int(lot_num_m.group(1)):04d}"

            start = m.end()
            nm = re.search(
                r"\n5\.1\s+Techninės\s+ID\s+dalies:\s*LOT", sec5[start:], re.IGNORECASE
            )
            end = start + nm.start() if nm else len(sec5)
            block = sec5[start:end]

            lot = lots_map.setdefault(lot_id, blank_lot())

            # Line-bounded one-liners
            m1 = re.search(r"Pavadinimas:\s*([^\n]+)", block, re.IGNORECASE)
            if m1:
                lot["Pavadinimas"] = m1.group(1).strip()

            # Description bounded until the next 5.1.x or a new major section digit
            m2 = re.search(
                r"Aprašymas:\s*(.+?)(?=\n(?:Vidaus\s+identifikatorius:|5\.1\.(?:1|2|3|4|5|6|7|8|9|10|15|16)|\n\d\.))",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if m2:
                lot["Aprašymas"] = norm_one_line(m2.group(1))

            m3 = re.search(r"Sutarties\s+objektas:\s*([^\n]+)", block, re.IGNORECASE)
            if m3:
                lot["Sutarties objektas"] = m3.group(1).strip()

            # CPV code + label (line-bounded)
            m4 = re.search(
                r"Pagrindinis\s+klasifikacijos\s+kodas\s*\(cpv\)\s*:\s*([0-9]{8})\s*([^\n]+)",
                block,
                re.IGNORECASE,
            )
            if m4:
                lot["Pagrindinis klasifikacijos kodas (cpv)"] = (
                    f"{m4.group(1)} {m4.group(2).strip()}"
                )

            # Place
            m5 = re.search(r"NUTS\):\s*([^\n]+)", block, re.IGNORECASE)
            if m5:
                lot["NUTS"] = m5.group(1).strip()

            m6 = re.search(r"Šalis:\s*([^\n]+)", block, re.IGNORECASE)
            if m6:
                lot["Šalis"] = m6.group(1).strip()

            # Optional: validity (months)
            galiojimas_m = re.search(
                r"Galiojimas:\s*(\d+)\s+Mėnuo", block, re.IGNORECASE
            )
            if galiojimas_m:
                try:
                    lot["Galiojimas (mėn.)"] = int(galiojimas_m.group(1))
                except Exception:
                    pass

            bendra = parse_bendra_informacija(block)
            lot["Bendra informacija"] = bendra
            if bendra["ES_fondai"] is not None:
                lot["ES_fondai"] = bendra["ES_fondai"]
            if bendra["SVP_taikoma"] is not None:
                lot["SVP_taikoma"] = bendra["SVP_taikoma"]

            # Strategy / GPP criteria (keep short; they can be verbose)
            svp = parse_strateginis_vp(block)
            if svp["tikslas"] is not None:
                lot["Strateginis tikslas"] = svp["tikslas"]
            if svp["aprasymas"] is not None:
                lot["Strateginis aprašymas"] = svp["aprasymas"]
            if svp["metodas"] is not None:
                lot["Poveikio aplinkai mažinimo metodas"] = svp["metodas"]
            if svp["zvp_kriterijai"] is not None:
                lot["ŽVP: kriterijai"] = svp["zvp_kriterijai"]

            # Criteria numeric weights
            crit_list, crit_summary = parse_criteria_section(block)
            if crit_list or crit_summary:
                lot["Skyrimo kriterijai"] = {
                    "santrauka": crit_summary or {},
                    "kriterijai": crit_list,
                }

    # =========================
    # PASS 2: Section 6 (results)
    # =========================
    if sec6:
        for m in re.finditer(
            r"pirkimo\s+dalies\s+ID:\s*(LOT[-\s]?0*\d+)", sec6, re.IGNORECASE
        ):
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

            # no-award message & reason
            mmsg = re.search(
                r"(Nepasirinktas?\s+n[ėe]\s+vienas\s+laim[ėe]tojas[^\n\r]*)",
                block,
                re.IGNORECASE,
            )
            if mmsg:
                lot["Rezultatas"]["Būsena"] = "neapdovanota"
                lot["Rezultatas"]["Žinutė"] = norm_one_line(mmsg.group(1))
                lot["Neapdovanota"] = True

            mreason = re.search(
                r"Priežastis[^:]*:\s*(.+?)\s*(?="
                r"\n\s*(?:"
                r"Laimėtoja(?:s|i)\b|"  # winners section
                r"pirkimo\s+dalies\s+ID\b|"  # next lot
                r"Rezultatai\b|"  # section header
                r"(?:Gauti|Gaut[ųu])\s+pasiūlym|"  # stats lines: Gauti / Gautų pasiūlymai …
                r"Statistin[ėe]\s+informacija|"  # 6.1.4 Statistinė informacija
                r"^\s*\d+(?:\.\d+){0,3}\s"  # any numbered heading like 6., 6.1, 6.1.4 …
                r")|\Z)",
                block,
                re.IGNORECASE | re.DOTALL | re.MULTILINE,
            )
            if mreason:
                reason_text = norm_one_line(mreason.group(1))
                lot["Rezultatas"]["Priežastis"] = reason_text
                lot["Neapdovanota priežastis"] = reason_text

            # bids/applications count
            mbids = re.search(
                r"Gaut[ųu]\s+pasiūlym[ųu].{0,120}?skaičius\s*:\s*([0-9]+)",
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if mbids:
                num = int(mbids.group(1))
                lot["Rezultatas"]["Statistika"][
                    "Gautų pasiūlymų ar dalyvavimo prašymų skaičius"
                ] = num
                lot["Statistika"][
                    "Gautų pasiūlymų ar dalyvavimo prašymų skaičius"
                ] = num

            # human-readable summary if applicable
            if lot["Rezultatas"]["Žinutė"] or lot["Rezultatas"]["Priežastis"]:
                parts = []
                if lot["Rezultatas"]["Žinutė"]:
                    parts.append(lot["Rezultatas"]["Žinutė"])
                if lot["Rezultatas"]["Priežastis"]:
                    parts.append(
                        "Priežastis, dėl kurios laimėtojas nebuvo pasirinktas: "
                        + lot["Rezultatas"]["Priežastis"]
                    )
                lot["Rezultatas_tekstas"] = " ".join(parts)

            # winners (skip if unawarded)

            if not lot["Neapdovanota"]:
                winner_blocks = re.split(
                    r"\bLaimėtoja(?:s|i)\b\s*:\s*", block, flags=re.IGNORECASE
                )
                for wb in winner_blocks[1:]:
                    item = parse_winner_block(wb)
                    if not item or not any(
                        [
                            item.get("Oficialus pavadinimas"),
                            item.get("Pasiūlymo identifikatorius"),
                            item.get("Pasiūlymo vertė (EUR)"),
                            item.get("Sutarties identifikatorius"),
                            item.get("Sutarties sudarymo data"),
                            item.get("Sutarties sudarymo datos"),
                            item.get("Laimėtojo pasirinkimo data"),
                        ]
                    ):
                        continue
                    lot["Info_winner"].append(item)

                # 👇 merge date-only items into the correct winner
                if lot["Info_winner"]:
                    lot["Info_winner"] = _merge_orphan_winner_items(lot["Info_winner"])
                    lot["Rezultatas"]["Būsena"] = "apdovanota"

    return lots_map if lots_map else None


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
                logging.warning(
                    "Empty text after extraction (method=%s) for %s", method, notice_id
                )
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
                # "buyer_name": buyer if buyer else None,
                "pirkimo_budas": budas if budas else None,
                "procedura_pagreitinta": (
                    pagreitinta if pagreitinta is not None else None
                ),
                "aprasymas": desc if desc else None,
                "lots": lots if lots else None,
                "viso_sutarciu_verte": (
                    viso_sutarciu_verte if viso_sutarciu_verte else None
                ),
            }

            db_update_partial(conn, notice_id, extracted, status="ok")
            logging.info(
                "OK notice_id=%s | method=%s | from=%s\nPreview: %s",
                notice_id,
                method,
                final_url,
                preview(text, 400),
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
