import { NextResponse } from 'next/server';
import { dbCVP } from '@/app/db/client';
import { CVPTable} from '@/app/db/schema';
import { desc, sql } from 'drizzle-orm';


export async function GET(request: Request) {
try{
const { searchParams} = new URL(request.url);

const rawLimit = Number(searchParams.get("limit"));
const rawOffset = Number(searchParams.get("offset"));

const DEFAULT_LIMIT = 10;
   const MAX_LIMIT = 100;

   const limit = Number.isFinite(rawLimit)
      ? Math.min(Math.max(rawLimit, 10), MAX_LIMIT)
      : DEFAULT_LIMIT;

const orderPrimary = desc(CVPTable.publish_date); 
const orderTie = desc(CVPTable.notice_id);   
const offset = Number.isFinite(rawOffset) && rawOffset >= 0 ? rawOffset : 0;

const rows = await (
    dbCVP.select().from(CVPTable).orderBy(orderPrimary, orderTie).limit(limit).offset(offset)
);

const [{ count }] = await (
    dbCVP.select({ count: sql<number>`count(*)` }).from(CVPTable)
);

 return NextResponse.json({
    rows,
    totalRows: Number(count),
   })
}
catch(err){
  console.log(err);
  return NextResponse.json(
    { error: "Failed to fetch"},
    { status: 500}
  )
}
}
