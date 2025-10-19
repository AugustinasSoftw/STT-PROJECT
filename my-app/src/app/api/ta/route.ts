import { NextResponse } from 'next/server';
import { dbTAR } from '@/app/db/client';
import { TAtable } from '@/app/db/schema';
import { and, desc, gte, ilike, sql } from 'drizzle-orm';

export async function GET(request: Request) {
try{
  const { searchParams} = new URL(request.url);
  

  const rawLimit = Number(searchParams.get("limit"));
  const rawOffset = Number(searchParams.get("offset"));

  const decodePlus = (v: string | null) => (v ? v.replace(/\+/g, " ").trim() : undefined); // + -> space

  const rusys = decodePlus(searchParams.get("rusys"));
  const highRisk = searchParams.has("dazniausiaiNaudNav");

   const DEFAULT_LIMIT = 10;
   const MAX_LIMIT = 100;

   const limit = Number.isFinite(rawLimit)
      ? Math.min(Math.max(rawLimit, 10), MAX_LIMIT)
      : DEFAULT_LIMIT;

   const orderPrimary = desc(TAtable.priemimo_data); 
   const orderTie     = desc(TAtable.id);   
   const offset = Number.isFinite(rawOffset) && rawOffset >= 0 ? rawOffset : 0;
   const whereRusys = rusys ? ilike(TAtable.rusis, `%${rusys}`) : undefined;
   const whereRisk = highRisk ? gte(TAtable.ai_risk_score, '0.7') : undefined; 
 // combine predicates
const whereAll =
  whereRusys && whereRisk ? and(whereRusys, whereRisk) : (whereRusys ?? whereRisk);

// rows
const rows = await (
  whereAll
    ? dbTAR.select().from(TAtable).where(whereAll).orderBy(orderPrimary, orderTie).limit(limit).offset(offset)
    : (await dbTAR.select().from(TAtable).orderBy(orderPrimary, orderTie).limit(limit).offset(offset))
);

// count
const [{ count }] = await (
  whereAll
    ? dbTAR.select({ count: sql<number>`count(*)` }).from(TAtable).where(whereAll)
    : dbTAR.select({ count: sql<number>`count(*)` }).from(TAtable)
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
