import { timestamp, pgTable, serial,date, integer, text, numeric, uuid, boolean, jsonb } from 'drizzle-orm/pg-core';

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

export const CVPTable = pgTable("notices_stage", {
  notice_id: text("notice_id").primaryKey(),        // TEXT PK

  title: text("title"),
  skelbimo_tipas: text("skelbimo_tipas"),

  // If your column is TIMESTAMP WITHOUT TIME ZONE:
  publish_date: date("publish_date"),
  // If it’s TIMESTAMPTZ, flip to { withTimezone: true }.

  pdf_url: text("pdf_urls"),
  buyer_name: text("buyer_name"),
  pirkimo_budas: text("pirkimo_budas"),
  procedura_pagreitinta: boolean("procedura_pagreitinta"),

  // Keep JSONB flexible but strongly typed on the TS side if you like:
  lots: jsonb("lots").$type<Record<string, unknown>>(),

  extractionStatus: text("extraction_status"),
  lastExtractedAt: timestamp("last_extracted_at", { withTimezone: false }),

  aprasymas: text("aprasymas"),

  // Can be number, array, or object—type to what you actually store:
  visoSutarciuVerte: jsonb("viso_sutarciu_verte").$type<unknown>(),
});


export type TableRow  = typeof TAtable.$inferSelect;
export type CVPRow = typeof CVPTable.$inferSelect