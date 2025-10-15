import psycopg2
from google import genai
import json
from google.genai.errors import ServerError, APIError
from dotenv import load_dotenv, find_dotenv
import os

# Gemini client
client = genai.Client(api_key="AIzaSyBIlyyKlXhGrfFpJkQO41RKRpGuaY4B-mk")

load_dotenv(find_dotenv())
DB_DSN = (os.getenv("DB_DSN") or os.getenv("DATABASE_URL") or "").strip()


# Process 10 batches; each batch reads 2 rows, updates them, then moves to the next 2
with psycopg2.connect(
    DB_DSN
) as conn:
    with conn.cursor() as cur:
        for _ in range(15):  # or while True
            # 1) fetch only unprocessed rows
            cur.execute(
                """
            SELECT id, pavadinimas
            FROM sprendimai
            WHERE ai_risk_score IS NULL
            AND (ai_summary IS NULL OR ai_summary = '')
            ORDER BY id
            LIMIT 2;
    """
            )
            rows = cur.fetchall()

            # 2) if nothing to do, stop — DO NOT call Gemini
            if not rows:
                break

            # 3) build prompt for just these rows
            items_text = "\n".join(f"{r[0]}. {r[1]}" for r in rows)
            prompt = f"""
Tu esi korumpuotos veiklos specialistas, tavo darbas aptikti galima teises aktuose korumpuota veikla.

Pateikiama 2 table eilutes:

{items_text}

For each entry, return a JSON object with:
- id
- short_risk_summary (<=40 words)
- chance (0..1)
- atsakymai turi buti pateikti lietuviu kalba

Output as a JSON array only.
"""

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.2
                    ),
                )

            except (ServerError, APIError) as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    print("Skipped this batch: model overloaded (503).")
                    continue  # go to next 2 rows
                raise

            data = json.loads(response.text)
            for item, src in zip(data, rows):
                row_id = src[0]  # DB id (int), not the model's
                chance = item.get("chance", item.get("Chance of corrupted activity"))
                summary = item["short_risk_summary"].strip()
                cur.execute(
                    "UPDATE sprendimai SET ai_risk_score = %s, ai_summary = %s WHERE id = %s;",
                    (round(float(chance), 3), summary, row_id),
                )
conn.commit()
