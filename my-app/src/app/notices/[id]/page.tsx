import { notFound } from "next/navigation";
import { dbCVP } from "@/app/db/client";
import { CVPTable } from "@/app/db/schema";
import { eq } from "drizzle-orm";
import NoticeClient from "./NoticeClient";
import { BugPlay } from "lucide-react";

export const revalidate = 300;

// --- 1️⃣ helper: collect winner names from the JSONB "lots" object
function getWinnerNamesFromLots(lots: unknown): string[] {
  if (!lots || typeof lots !== "object") return [];
  const names: string[] = [];

  for (const lot of Object.values(lots as Record<string, any>)) {
    const winners = Array.isArray(lot?.["Info_winner"]) ? lot["Info_winner"] : [];
    for (const w of winners) {
      const name = w?.["Oficialus pavadinimas"];
      if (typeof name === "string" && name.trim()) {
        names.push(name.trim());
      }
    }
  }
  return [...new Set(names)];
}

// --- 2️⃣ helper: check if the first LOT has an "unawarded" result
function hasUnawardedResult(lots: unknown): boolean {
  if (!lots || typeof lots !== "object") return false;

  const lot1 = (lots as Record<string, any>)["LOT-0001"];
  if (!lot1) return false;

  const resultText = lot1["Rezultatas_tekstas"];
  if (typeof resultText !== "string") return false;

  return resultText.includes("Nepasirinktas nė vienas laimėtojas ir konkursas baigtas");
}

export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const decodedId = decodeURIComponent(id);

  // 3️⃣ fetch the current notice
  const [row] = await dbCVP
    .select()
    .from(CVPTable)
    .where(eq(CVPTable.notice_id, decodedId))
    .limit(1);

  if (!row) return notFound();

  // 4️⃣ collect winner names from this notice
  const currentWinners = new Set(getWinnerNamesFromLots(row.lots));

  // 5️⃣ fetch same-buyer rows and find matches + count unawarded
  let matches: typeof row[] = [];
  let sameBuyerCount = 0;
  let unawardedCount = 0;

  if (row.buyer_name && currentWinners.size > 0) {
    const sameBuyerRows = await dbCVP
      .select()
      .from(CVPTable)
      .where(eq(CVPTable.buyer_name, row.buyer_name));

    sameBuyerCount = sameBuyerRows.length;
    unawardedCount = sameBuyerRows.filter((r) => hasUnawardedResult(r.lots)).length;

    matches = sameBuyerRows.filter((r) => {
      if (r.notice_id === row.notice_id) return false; // exclude self
      const winners = getWinnerNamesFromLots(r.lots);
      return winners.some((n) => currentWinners.has(n));
    });
  }

  // 6️⃣ serialize props for client
  const props = {
    ...row,
    notice_id: row.notice_id,
    title: row.title,
    publish_date: row.publish_date ?? null,
    skelbimo_tipas: row.skelbimo_tipas,
    pdf_url: row.pdf_url,
    buyer_name: row.buyer_name,
    pirkimo_budas: row.pirkimo_budas,
    procedura_pagreitinta: row.procedura_pagreitinta,
    lots: row.lots,
    aprasymas: row.aprasymas,
    visoSutarciuVerte: row.visoSutarciuVerte,
  };

  return <NoticeClient rowValue={props} matches={matches} sameBuyerCount={sameBuyerCount} unawardedCount={unawardedCount}/>;
}
