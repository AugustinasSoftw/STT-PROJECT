import { timestamp, pgTable, serial,date, integer, text, numeric, uuid, boolean } from 'drizzle-orm/pg-core';

export const TAtable = pgTable('sprendimai', {
  id: serial('id').primaryKey(),
  eil_nr: integer('eil_nr').notNull(),
  rusis: text('rusis').notNull(),
  pavadinimas: text('pavadinimas').notNull(),
  istaigos_nr: text('istaigos_nr').notNull(),
  priemimo_data: date('priemimo_data').notNull(),
  isigaliojimo_data: date('isigaliojimo_data').notNull(),
  projektai_nuoroda: text('projektai_nuoroda'),
  scraped_at: timestamp('scraped_at'),
  ai_risk_score: numeric('ai_risk_score'),
  ai_summary: text('ai_summary'),

});

export const CVPTable = pgTable("awards", {
  id: uuid("id").defaultRandom().primaryKey(),

  notice_id: text("notice_id"),
  lot_no: text("lot_no"),
  lot_title: text("lot_title"),

  buyer_name: text("buyer_name"),
  buyer_code: text("buyer_code"),
  title: text("title"),
  cpv: text("cpv"),

  publish_date: date("publish_date"),
  award_date: date("award_date"),

  winner_name: text("winner_name"),
  winner_code: text("winner_code"),
  award_value_eur: numeric("award_value_eur", { precision: 14, scale: 2 }),
  offers_count: integer("offers_count"),

  procedure_type: text("procedure_type"),
  procedure_title: text("procedure_title"),
  procedure_description: text("procedure_description"),

  previous_notice_id: text("previous_notice_id"),
  procedure_accelerated: boolean("procedure_accelerated"),

  notice_url: text("notice_url"),
  pdf_url: text("pdf_url"),

  source: text("source").notNull().default("cvpis"),
  ingested_at: timestamp("ingested_at", { withTimezone: true }).notNull().defaultNow(),

  sha256_text: text("sha256_text"), // drizzle doesn’t have bytea, store as text (base64/hex)
});


export type TableRow  = typeof TAtable.$inferSelect;
export type CVPRow = typeof CVPTable.$inferSelect