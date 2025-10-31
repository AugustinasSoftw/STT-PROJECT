from dotenv import load_dotenv, find_dotenv
import os, json, psycopg2, psycopg2.extras
from collections import defaultdict
from datetime import date, timedelta

load_dotenv(find_dotenv(usecwd=True))
DSN = os.getenv("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL not set")

THRESHOLD = float(os.getenv("F1_THRESHOLD", "0.30"))
WINDOW_START = date.today() - timedelta(days=365)


def notice_status_from_lots(lots):
    """accepted=True if ANY lot is apdovanota; cancelled=True if ALL lots are neapdovanota"""
    if not lots:
        return (False, False)
    any_awarded = False
    all_cancelled = True

    for _, lot in lots.items():
        res = (lot or {}).get("Rezultatas", {}) or {}
        busena = (res.get("Būsena") or "").strip().lower()
        neapd = lot.get("Neapdovanota")

        is_awarded = busena.startswith("apdovanota")
        is_cancelled = busena.startswith("neapdovanota") or (neapd is True)

        if is_awarded:
            any_awarded = True
        if not is_cancelled:
            all_cancelled = False

    return (any_awarded, all_cancelled)


def compute_flag_data(rows):
    """Compute counts for accepted/cancelled per buyer"""
    buyer_counts = defaultdict(lambda: {"acc": 0, "canc": 0})

    for row in rows:
        buyer = row["buyer_name"]
        lots = row["lots"]

        if isinstance(lots, str):
            try:
                lots = json.loads(lots)
            except Exception:
                lots = {}

        accepted, cancelled = notice_status_from_lots(lots)

        if cancelled:
            buyer_counts[buyer]["canc"] += 1
        elif accepted:
            buyer_counts[buyer]["acc"] += 1

    return buyer_counts


def update_json(cur, buyer_counts, column_name):
    """Write computed data to DB"""
    for buyer, c in buyer_counts.items():
        acc, canc = c["acc"], c["canc"]
        ratio = (canc / acc) if acc > 0 else 0
        flag = ratio > THRESHOLD

        cur.execute(
            f"""
            UPDATE notices_stage
            SET {column_name} = jsonb_build_object(
                'f1_flag', %s,
                'f1_cancelled_count', %s,
                'f1_accepted_count', %s,
                'f1_ratio_value', %s,
                'f1_ratio_threshold', %s
            )
            WHERE buyer_name = %s;
            """,
            (flag, canc, acc, ratio, THRESHOLD, buyer),
        )


def main():
    with psycopg2.connect(DSN) as conn, conn.cursor(
        cursor_factory=psycopg2.extras.DictCursor
    ) as cur:
        cur.execute("SELECT buyer_name, lots, publish_date FROM notices_stage;")
        rows = cur.fetchall()

        # ----- ALL data -----
        buyer_counts_all = compute_flag_data(rows)
        update_json(cur, buyer_counts_all, "f1_data")

        # ----- LAST YEAR data -----
        rows_last_year = [
            r for r in rows if r["publish_date"] and r["publish_date"] >= WINDOW_START
        ]
        buyer_counts_last = compute_flag_data(rows_last_year)
        update_json(cur, buyer_counts_last, "f1_data_lastyear")

        print(f"✅ Updated F1 for {len(buyer_counts_all)} buyers (all time)")
        print(
            f"✅ Updated F1_lastyear for {len(buyer_counts_last)} buyers since {WINDOW_START}"
        )


if __name__ == "__main__":
    main()
