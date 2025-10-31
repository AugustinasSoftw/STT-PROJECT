from dotenv import load_dotenv, find_dotenv
import os, psycopg2

load_dotenv(find_dotenv(usecwd=True))
dsn = os.getenv("DATABASE_URL")

sql = """
ALTER TABLE notices_stage
  ADD COLUMN IF NOT EXISTS F3_data boolean;

WITH per AS (
  SELECT
    n.notice_id,
    COUNT(*) AS lot_count,
    SUM(
      CASE
        WHEN COALESCE(
               NULLIF(lot.value->'Rezultatas'->'Statistika'->>'Gautų pasiūlymų ar dalyvavimo prašymų skaičius','')::int,
               NULLIF(lot.value->'Statistika'->>'Gautų pasiūlymų ar dalyvavimo prašymų skaičius','')::int
             ) = 1
        THEN 1 ELSE 0
      END
    ) AS ones_count
  FROM notices_stage n
  JOIN LATERAL jsonb_each(n.lots) AS lot(key, value) ON TRUE
  GROUP BY n.notice_id
)
UPDATE notices_stage n
SET F3_data = (per.ones_count = per.lot_count AND per.lot_count > 0)
FROM per
WHERE n.notice_id = per.notice_id;
"""

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute(sql)
print("✅ F3_data computed for all notices.")
