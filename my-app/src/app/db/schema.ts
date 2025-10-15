import { timestamp, pgTable, serial,date, integer, text, numeric } from 'drizzle-orm/pg-core';

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

export type TableRow  = typeof TAtable.$inferSelect;
export type NewTable  = typeof TAtable.$inferSelect;