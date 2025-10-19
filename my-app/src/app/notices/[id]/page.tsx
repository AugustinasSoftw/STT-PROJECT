import { notFound } from "next/navigation";
import { dbCVP } from "@/app/db/client";
import { CVPTable } from "@/app/db/schema";
import { eq } from "drizzle-orm";
import NoticeClient from "./NoticeClient"; // client component below

export const revalidate = 300; // optional ISR

export default async function Page({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);

  const [row] = await dbCVP
    .select()
    .from(CVPTable)
    .where(eq(CVPTable.notice_id, id))
    .limit(1);

  if (!row) return notFound();

  // ✅ serialize everything that isn’t JSON-safe
  const props = {
    ...row,
    publish_date: row.publish_date ?? null,
    award_date: row.award_date ?? null,
    award_value_eur: row.award_value_eur?.toString() ?? null,
    ingested_at:
      (row as any).ingested_at?.toISOString?.() ??
      (typeof (row as any).ingested_at === "string"
        ? (row as any).ingested_at
        : null),
    sha256_text: row.sha256_text ? String(row.sha256_text) : null,
  };

  return <NoticeClient rowValue={props} />; // pass to client
}
