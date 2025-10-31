"use client";

import { CVPRow } from "@/app/db/schema";
import { SaveButton } from "./SaveButton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import Link from "next/link";
import { FaRegFile } from "react-icons/fa";

/* -------------------------------------------------------------------------- */
/*                                UTILITIES                                   */
/* -------------------------------------------------------------------------- */

const norm = (s: string) =>
  s.normalize("NFC").replace(/\s+/g, " ").trim().toLowerCase();

const safeGet = (obj: any, wanted: string) => {
  if (!obj || typeof obj !== "object") return undefined;
  const hit = Object.keys(obj).find((k) => norm(k) === norm(wanted));
  return hit ? (obj as any)[hit] : undefined;
};

const safeGetAny = (obj: any, aliases: string[]) => {
  for (const a of aliases) {
    const v = safeGet(obj, a);
    if (v !== undefined && v !== null && v !== "") return v;
  }
  return undefined;
};

const getByPath = (obj: any, path: string[]) =>
  path.reduce<any>(
    (acc, key) => (acc == null ? undefined : safeGet(acc, key)),
    obj
  );

const toArray = <T = any>(v: any): T[] =>
  Array.isArray(v) ? v : v == null ? [] : [v];

const tri = (v: any) => (v === true ? "Taip" : v === false ? "Ne" : "-");

/* -------------------------------------------------------------------------- */
/*                             UI PRIMITIVES                                  */
/* -------------------------------------------------------------------------- */

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-lg font-semibold tracking-tight text-zinc-200 flex items-center gap-2">
      <span className="h-4 w-1.5 rounded bg-zinc-700" />
      {children}
    </h2>
  );
}

function SectionCard({
  title,
  children,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur supports-[backdrop-filter]:bg-zinc-900/30 p-5 space-y-4">
      {typeof title === "string" ? <Heading>{title}</Heading> : title}
      {children}
    </section>
  );
}

/** Label/value row */
function KV({
  label,
  children,
}: {
  label: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[220px_1fr] gap-x-4 gap-y-1 py-2 border-b border-zinc-800/60 last:border-0">
      <dt className="text-zinc-400">{label}</dt>
      <dd className="text-zinc-100">{children}</dd>
    </div>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-zinc-700 px-2.5 py-0.5 text-xs text-zinc-200">
      {children}
    </span>
  );
}

/** Render a single value from a source using alias keys */
function FieldValue({
  source,
  aliases,
  fallback = "-",
}: {
  source: any;
  aliases: string[];
  fallback?: React.ReactNode;
}) {
  const v = safeGetAny(source, aliases);
  return <>{v ?? fallback}</>;
}

/** Robust renderer for sections that may contain one-or-many objects */
function ArraySection({
  lot,
  title,
  path, // e.g. ["Skyrimo kriterijai", "kriterijai"]
  fields, // [{label, aliases}]
}: {
  lot: any;
  title: string;
  path: string[];
  fields: { label: string; aliases: string[] }[];
}) {
  const arr = toArray(getByPath(lot, path));
  const container = safeGet(lot, path[0]); // fallback when array missing
  const effective = arr.length ? arr : toArray(container);

  // Keep only rows where at least ONE of the selected fields has a real value
  const hasValue = (v: any) =>
    v !== undefined && v !== null && String(v).trim() !== "";

  const filtered = effective.filter((item) =>
    fields.some(({ aliases }) => hasValue(safeGetAny(item, aliases)))
  );

  return (
    <SectionCard title={title}>
      {filtered.length === 0 ? (
        <p className="text-zinc-400">-</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-zinc-800/70">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900/50 text-zinc-400">
              <tr>
                {fields.map((f) => (
                  <th key={f.label} className="py-2 px-3 text-left">
                    {f.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((item: any, i: number) => (
                <tr key={i} className="border-t border-zinc-800/60">
                  {fields.map(({ label, aliases }) => {
                    const v = safeGetAny(item, aliases);
                    return (
                      <td key={label} className="py-2 px-3">
                        {hasValue(v) ? String(v) : "-"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  );
}

/* -------------------------------------------------------------------------- */
/*                               MAIN COMPONENT                               */
/* -------------------------------------------------------------------------- */

type Props = {
  rowValue: CVPRow;
  matches: CVPRow[];
  sameBuyerCount: number;
  unawardedCount: number;
};

export default function NoticeClient({
  rowValue,
  matches,
}: Props) {
  return (
    <main className=" space-y-8 mx-auto p-10">
      {/* Header */}
      <header className="flex items-center justify-between">
        <div className="flex flex-row gap-3">
          <h1 className="text-2xl font-semibold">
            Notice {rowValue.notice_id}
          </h1>
        </div>

        <SaveButton rowValue={{ id: rowValue.notice_id, ...rowValue }} />
      </header>

      {/* Summary grid */}
      <section className="grid md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur p-4">
          <div className="text-xs dark:text-zinc-500">Pranešimo ID</div>
          <div className="text-sm dark:text-zinc-300">
            <Link
              className="text-blue-400 underline hover:opacity-80"
              href={rowValue.pdf_url || ""}
            >
              {rowValue.notice_id || "-"}
            </Link>
          </div>
        </div>
        <Field label="Pranešimo tipas" value={rowValue.skelbimo_tipas} />
        <Field label="Pranešimo pavadinimas" value={rowValue.title} />
        <Field label="PV" value={rowValue.buyer_name} />
        <Field label="Publish Date" value={rowValue.publish_date} />
      </section>

      {/* Lots */}
      {rowValue.lots &&
        Object.entries(rowValue.lots as Record<string, any>).map(
          ([lotKey, lot]) => (
            <Accordion
              key={lotKey}
              type="single"
              collapsible
              className="w-full border border-zinc-800/80 rounded-xl overflow-hidden"
            >
              <AccordionItem value={lotKey}>
                <AccordionTrigger className="text-base font-medium px-5 py-4 bg-zinc-900/40 hover:bg-zinc-900/60 transition">
                  <div className="flex items-center gap-3">
                    <Pill>5.1</Pill>
                    <span>Techninės ID dalies: {lotKey}</span>
                  </div>
                </AccordionTrigger>

                <AccordionContent className="p-5 space-y-6">
                  {/* 5.1 Base info */}
                  <SectionCard title="5.1 Pagrindinė informacija">
                    <dl className="divide-y divide-transparent">
                      <KV label={<strong>Pavadinimas</strong>}>
                        {lot?.Pavadinimas ?? "-"}
                      </KV>
                      <KV label={<strong>Aprašymas</strong>}>
                        {lot?.Aprašymas ?? "-"}
                      </KV>
                      <KV label={<strong>Būsena</strong>}>
                        {lot?.Rezultatas?.Būsena ? (
                          <Pill>{lot?.Rezultatas?.Būsena}</Pill>
                        ) : (
                          "-"
                        )}
                      </KV>
                    </dl>
                  </SectionCard>

                  {/* 5.1.1 Tikslas */}
                  <SectionCard title="5.1.1 Tikslas">
                    <dl>
                      <KV label={<strong>Sutarties objektas</strong>}>
                        {lot?.["Sutarties objektas"] ?? "-"}
                      </KV>
                      <KV
                        label={
                          <strong>Pagrindinis klasifikacijos kodas (CPV)</strong>
                        }
                      >
                        <code className="font-mono text-sm text-zinc-200">
                          {lot?.["Pagrindinis klasifikacijos kodas (cpv)"] ??
                            "-"}
                        </code>
                      </KV>
                    </dl>
                  </SectionCard>

                  {/* 5.1.2 Vieta */}
                  <SectionCard title="5.1.2 Sutarties vykdymo vieta">
                    <dl>
                      <KV label={<strong>NUTS</strong>}>
                        {lot?.NUTS ?? "-"}
                      </KV>
                      <KV label={<strong>Šalis</strong>}>
                        {lot?.Šalis ?? "-"}
                      </KV>
                    </dl>
                  </SectionCard>

                  {/* 5.1.6 Bendra informacija */}
                  <SectionCard title="5.1.6 Bendra informacija">
                    <dl>
                      <KV label={<strong>Pirma eilutė</strong>}>
                        {lot?.["Bendra informacija"]?.pirma_eilute ?? "-"}
                      </KV>
                      <KV label={<strong>Pirkimui taikoma SVP</strong>}>
                        {tri(lot?.["Bendra informacija"]?.SVP_taikoma)}
                      </KV>
                    </dl>
                  </SectionCard>

                  {/* 5.1.7 Strateginis pirkimas */}
                  <SectionCard title="5.1.7 Strateginis viešasis pirkimas">
                    <dl>
                      <KV label={<strong>Tikslas</strong>}>
                        <FieldValue
                          source={lot}
                          aliases={[
                            "Strateginis tikslas",
                            "Strateginio viešojo pirkimo tikslas",
                          ]}
                        />
                      </KV>
                      <KV label={<strong>Aprašymas</strong>}>
                        <FieldValue source={lot} aliases={["Aprašymas"]} />
                      </KV>
                    </dl>
                  </SectionCard>

                  {/* 5.1.10 Skyrimo kriterijai */}
                  <ArraySection
                    lot={lot}
                    title="5.1.10 Skyrimo kriterijai"
                    path={["Skyrimo kriterijai", "kriterijai"]}
                    fields={[
                      { label: "Rūšis", aliases: ["Rūšis"] },
                      { label: "Aprašymas", aliases: ["Aprašymas"] },
                      {
                        label: "Kategorija skyrimo kriterijaus",
                        aliases: ["Kategorija_eilutė", "Kategorija eilutė"],
                      },
                      
                    ]}
                  />
                   {(() => {
  const winners = toArray(safeGet(lot, "Info_winner"));
  const stats =
    safeGet(lot, "Statistika") ??
    safeGet(safeGet(lot, "Rezultatas"), "Statistika") ??
    {};

  // If there are winners, merge stats into each winner row.
  // If no winners but we have stats, show one row with just stats.
  const combined = winners.length
    ? winners.map((w) => ({ ...w, ...stats }))
    : Object.keys(stats).length
    ? [stats]
    : [];

  return (
    <ArraySection
      lot={{ combined }}
      title="Informacija apie laimėtojus ir statistika"
      path={["combined"]}
      fields={[
        {
          label: "Oficialus pavadinimas",
          aliases: ["Oficialus pavadinimas"],
        },
        {
          label: "Pasiūlymo vertė (EUR)",
          aliases: ["Pasiūlymo vertė (EUR)"],
        },
        {
          label: "Pasiūlymo identifikatorius",
          aliases: ["Pasiūlymo identifikatorius"],
        },
        {
          label: "Sutarties sudarymo datos",
          aliases: ["Sutarties sudarymo datos"],
        },
        {
          label: "Gautų pasiūlymų ar dalyvavimo prašymų skaičius",
          aliases: ["Gautų pasiūlymų ar dalyvavimo prašymų skaičius"],
        },
      ]}
    />
  );
})()}
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          )
        )}

      {/* History */}
      <section className="rounded-xl border border-zinc-800 p-5">
        <h2 className="text-lg font-semibold mb-3">Pirkėjo/Tiekėjo istorija</h2>
        <div className="text-sm dark:text-zinc-400">
          {matches.length > 0 ? (
            <div className="overflow-hidden rounded-lg border border-zinc-800/70">
              <table className="w-full text-left border-collapse text-sm">
                <thead className="bg-zinc-900/50 text-zinc-400">
                  <tr>
                    <th className="py-2 px-3">Paskelbimo Data</th>
                    <th className="py-2 px-3">Pranešimo ID</th>
                    <th className="py-2 px-3">PV</th>
                    <th className="py-2 px-3">Pavadinimas</th>
                    <th className="py-2 px-3">Sutartis</th>
                    <th className="py-2 px-3">Visa sutarčių vertė</th>
                  </tr>
                </thead>
                <tbody>
                  {matches.map((m) => (
                    <tr key={m.notice_id} className="border-t border-zinc-800/60">
                      <td className="py-2 px-3">{m.publish_date}</td>
                      <td className="py-2 px-3">
                        <Link
                          target="_blank"
                          href={`/notices/${encodeURIComponent(m.notice_id)}`}
                          prefetch
                          className="text-blue-400 underline hover:opacity-80"
                        >
                          {m.notice_id}
                        </Link>
                      </td>
                      <td className="py-2 px-3">{m.buyer_name}</td>
                      <td className="py-2 px-3">{m.aprasymas}</td>
                      <td className="py-2 px-3">
                        {m.pdf_url ? (
                          <Link
                            href={m.pdf_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center"
                          >
                            <FaRegFile />
                          </Link>
                        ) : (
                          <span>-</span>
                        )}
                      </td>
                      <td className="py-2 px-3">
                        {m.visoSutarciuVerte?.amount
                          ? `${Number(
                              m.visoSutarciuVerte.amount
                            ).toLocaleString()} ${m.visoSutarciuVerte.currency}`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>No matches found</p>
          )}
        </div>
      </section>
    </main>
  );
}

/* Simple stateless field card (used in summary grid) */
function Field({ label, value }: { label: string; value: any }) {
  return (
    <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 backdrop-blur p-4">
      <div className="text-xs dark:text-zinc-500">{label}</div>
      <div className="text-sm dark:text-zinc-300">{value ?? "-"}</div>
    </div>
  );
}
