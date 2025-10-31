from dotenv import load_dotenv, find_dotenv
import os, psycopg2

load_dotenv(find_dotenv(usecwd=True))
dsn = os.getenv("DATABASE_URL")

with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute(
        """
    ALTER TABLE notices_stage ADD COLUMN IF NOT EXISTS f2_data jsonb;

    UPDATE notices_stage
    SET f2_data = jsonb_build_object(
      'f2_flag_non_open',
      CASE
        WHEN pirkimo_budas ILIKE '%Atviras%' THEN FALSE
        WHEN pirkimo_budas ILIKE '%Derybos su išankstiniu kvietimu%'
          OR pirkimo_budas ILIKE '%konkursas su derybomis%' THEN TRUE
        WHEN pirkimo_budas ILIKE '%Derybos be išankstinio skelbimo%'
          OR pirkimo_budas ILIKE '%Derybos be isankstinio skelbimo%' THEN TRUE
        WHEN pirkimo_budas ILIKE '%Ribotas%' THEN TRUE
        WHEN pirkimo_budas IS NULL OR btrim(pirkimo_budas) = '' THEN NULL
        ELSE NULL
      END,
      'f2_category',
      CASE
        WHEN pirkimo_budas ILIKE '%Atviras%' THEN 'Atviras'
        WHEN pirkimo_budas ILIKE '%Derybos su išankstiniu kvietimu%'
          OR pirkimo_budas ILIKE '%konkursas su derybomis%'
          THEN 'Derybos su išankstiniu kvietimu dalyvauti konkurse ir (arba) konkursas su derybomis'
        WHEN pirkimo_budas ILIKE '%Derybos be išankstinio skelbimo%'
          OR pirkimo_budas ILIKE '%Derybos be isankstinio skelbimo%'
          THEN 'Derybos be išankstinio skelbimo apie pirkimą'
        WHEN pirkimo_budas ILIKE '%Ribotas%' THEN 'Ribotas'
        WHEN pirkimo_budas IS NULL OR btrim(pirkimo_budas) = '' THEN 'NULL'
        ELSE pirkimo_budas
      END
    )
    WHERE f2_data IS NULL;
    """
    )
print("✅ F2 data updated only for empty rows")
