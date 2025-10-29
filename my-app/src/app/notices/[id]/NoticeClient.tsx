"use client";
import { CVPRow } from "@/app/db/schema";

import { useState } from "react";
import { SaveButton } from "./SaveButton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

type Props = {
  rowValue: CVPRow;
  matches: CVPRow[];
  sameBuyerCount: number;
  unawardedCount: number;
};

export default function NoticeClient({
  rowValue,
  matches,
  sameBuyerCount,
  unawardedCount,
}: Props) {
  // Mock AI & historical analysis

  const supplierHistory = [
    { year: 2021, contracts: 4, total: 650000 },
    { year: 2022, contracts: 6, total: 810000 },
    { year: 2023, contracts: 8, total: 950000 },
    { year: 2024, contracts: 11, total: 1280000 },
  ];
  console.log(matches);
  console.log(sameBuyerCount);
  console.log(unawardedCount);

  return (
    <main className="p-8 space-y-8">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div className="flex flex-row gap-3">
          <h1 className="text-2xl font-semibold">
            Notice {rowValue.notice_id}
          </h1>
        </div>

        <div>
          <SaveButton rowValue={{ id: rowValue.notice_id, ...rowValue }} />
        </div>
      </header>

      {/* Summary grid */}
      <section className="grid md:grid-cols-2 gap-6">
        <Field label="Pranešimo ID" value={rowValue.notice_id} />
        <Field label="Pranešimo tipas" value={rowValue.skelbimo_tipas} />
        <Field label="Pranešimo pavadinimas" value={rowValue.title} />
        <Field label="PV" value={rowValue.buyer_name} />
        <Field label="Publish Date" value={rowValue.publish_date} />
      </section>

      {rowValue.lots &&
        Object.entries(rowValue.lots as Record<string, any>).map(
          ([lotKey, lot]) => (
            <Accordion
              key={lotKey}
              type="single"
              collapsible
              className="w-full border-b border-zinc-800 last:border-0"
            >
              <AccordionItem value={lotKey} className="">
                <AccordionTrigger>
                  {lotKey}: {lot?.Pavadinimas ?? "Be pavadinimo"}
                </AccordionTrigger>

                <AccordionContent className="flex flex-col gap-3">
                  <p>
                    <strong>Aprašymas:</strong> {lot?.Aprašymas ?? "—"}
                  </p>
                  <p>
                    <strong>Šalis:</strong> {lot?.Šalis ?? "—"}
                  </p>

                  {/* winners list */}
                  {Array.isArray(lot?.Info_winner) &&
                  lot.Info_winner.length > 0 ? (
                    <ul className="list-disc ml-5">
                      {lot.Info_winner.map((w: any, i: number) => (
                        <li key={i}>
                          {w["Oficialus pavadinimas"] ?? "—"}
                          {w["Pasiūlymo vertė (EUR)"] != null && (
                            <>
                              {" "}
                              —{" "}
                              {Number(
                                w["Pasiūlymo vertė (EUR)"]
                              ).toLocaleString()}{" "}
                              €
                            </>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground text-sm">
                      No winners listed
                    </p>
                  )}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )
        )}
      {/* Supplier History */}
      <section className="rounded-xl border border-zinc-800 p-5">
        <h2 className="text-lg font-semibold mb-3">Supplier History</h2>
        <div className="text-sm dark:text-zinc-400">
          {matches.length > 0 ? (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 dark:text-zinc-500">
                  <th className="pb-2">Year</th>
                  <th className="pb-2">Contracts</th>
                  <th className="pb-2">Total Value (€)</th>
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.notice_id} className="border-b border-zinc-900">
                    <td className="py-1">{m.publish_date}</td>
                    <td className="py-1">{m.notice_id}</td>
                    <td className="py-1">{m.buyer_name}</td>
                    <td className="py-1">{m.aprasymas}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>No matches found</p>
          )}
        </div>
      </section>
    </main>
  );
}

/* 🔹 COMPONENTS */

function Field({ label, value }: any) {
  return (
    <div className="rounded-lg border border-zinc-800 p-4">
      <div className="text-xs dark:text-zinc-500">{label}</div>
      <div className="text-sm dark:text-zinc-300">{value || "-"}</div>
    </div>
  );
}

function RiskBadge({ score }: any) {
  let label = "Low Risk";
  let color = "bg-green-500/20 text-green-400";

  if (score > 0.4 && score <= 0.7)
    (label = "Medium Risk"), (color = "bg-yellow-500/20 text-yellow-400");
  else if (score > 0.7)
    (label = "High Risk"), (color = "bg-red-500/20 text-red-400");

  return (
    <span
      className={`px-3 flex justify-center items-center rounded-full text-sm font-medium ${color}`}
    >
      {label} ({Math.round(score * 100)}%)
    </span>
  );
}
