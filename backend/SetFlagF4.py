from dotenv import load_dotenv, find_dotenv
import os, psycopg2

load_dotenv(find_dotenv(usecwd=True))
DSN = os.getenv("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL not set")

SQL = """
WITH
-- 1) Extract awarded lots and winner company names
lot_winners AS (
  SELECT
    n.notice_id,
    lot.key AS lot_id,
    lower(btrim(winner->>'Oficialus pavadinimas')) AS supplier_name
  FROM notices_stage n
  JOIN LATERAL jsonb_each(n.lots) AS lot(key, value) ON TRUE
  LEFT JOIN LATERAL jsonb_array_elements(lot.value->'Info_winner') AS winner ON TRUE
  WHERE (lot.value->'Rezultatas'->>'Būsena') ILIKE 'apdovanota%%'
),
-- 2) Count how many lots each supplier won in a notice
supplier_lot_counts AS (
  SELECT
    notice_id,
    supplier_name,
    COUNT(DISTINCT lot_id) AS lots_won
  FROM lot_winners
  WHERE supplier_name IS NOT NULL AND supplier_name <> ''
  GROUP BY notice_id, supplier_name
),
-- 3) Summarize notice-level stats
notice_stats AS (
  SELECT
    lw.notice_id,
    COUNT(DISTINCT lw.lot_id) AS awarded_lots,
    COALESCE(MAX(slc.lots_won), 0) AS max_lots_by_one_supplier
  FROM lot_winners lw
  LEFT JOIN supplier_lot_counts slc
    ON slc.notice_id = lw.notice_id
   AND slc.supplier_name = lw.supplier_name
  GROUP BY lw.notice_id
),
-- 4) Identify the top supplier per notice
top_supplier AS (
  SELECT DISTINCT ON (notice_id)
    notice_id, supplier_name, lots_won
  FROM supplier_lot_counts
  ORDER BY notice_id, lots_won DESC, supplier_name
),

-- 5) Perform both updates
updated_f4 AS (
  UPDATE notices_stage n
  SET F4_dominant_supplier = (ns.awarded_lots >= 2 AND ns.max_lots_by_one_supplier >= 2)
  FROM notice_stats ns
  WHERE n.notice_id = ns.notice_id
    AND n.F4_dominant_supplier IS NULL
  RETURNING n.notice_id
)
UPDATE notices_stage n
SET f4_data = jsonb_build_object(
    'dominant_supplier', ts.supplier_name,
    'lots_won', ts.lots_won
)
FROM top_supplier ts
WHERE n.notice_id = ts.notice_id
  AND n.f4_data IS NULL;
"""


def main():
    with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(SQL)
        print("✅ F4_dominant_supplier and f4_data updated successfully.")


if __name__ == "__main__":
    main()
