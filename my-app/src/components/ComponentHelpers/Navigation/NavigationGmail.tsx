import { useState } from "react";

type Row = {
  id: string | number;
  pavadinimas: string;
  istaigos_nr: string;
  priemimo_data: string;
  ai_risk_score: any;
};

export default function NavigationGmail({
  rows,
  onCancel,
  onDone,
}: {
  rows: Row[];
  onCancel: () => void;
  onDone: () => void;
}) {
  const [to, setTo] = useState("");
  const [note, setNote] = useState("");

  const subject = 'TAR dokumentai';
  const body =
    `${note ? note + "\n\n" : ""}Pasirinkti dokumentai (${rows.length}):\n` +
    rows
      .map(
        (r, i) =>
          `${i + 1}. ${r.pavadinimas} — Įstaigos Nr.: ${r.istaigos_nr} — Priėmimo data: ${r.priemimo_data} - Korupcijos rizika: ${r.ai_risk_score} `
      )
      .join("\n");

  const send = () => {
    const gmailUrl =
      `https://mail.google.com/mail/?view=cm&fs=1` +
      `&to=${encodeURIComponent(to)}` +
      `&su=${encodeURIComponent(subject)}` +
      `&body=${encodeURIComponent(body)}`;
    const mailtoUrl =
      `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

    const w = window.open(gmailUrl, "_blank", "noopener,noreferrer");
    if (!w) window.location.href = mailtoUrl;

    onDone();
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm mb-1">Gavėjo el. paštas</label>
        <input
          type="email"
          placeholder="vardas@pavyzdys.lt, kitas@..."
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="w-full rounded-lg bg-zinc-700 px-3 py-2 outline-none ring-1 ring-zinc-600 focus:ring-zinc-400"
        />
      </div>

      <div>
        <label className="block text-sm mb-1">Žinutė (pasirenkama)</label>
        <textarea
          rows={4}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="w-full rounded-lg bg-zinc-700 px-3 py-2 outline-none ring-1 ring-zinc-600 focus:ring-zinc-400"
        />
      </div>

      <div className="text-xs text-zinc-300">
        <p className="font-medium mb-1">Peržiūra:</p>
        <pre className="whitespace-pre-wrap bg-black/20 rounded-lg p-3 max-h-40 overflow-auto">
          Subject: {subject}{"\n\n"}{body}
        </pre>
      </div>

      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="rounded-lg px-3 py-2 bg-zinc-700 hover:bg-zinc-600">
          Atgal
        </button>
        <button onClick={send} className="rounded-lg px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white">
          Siųsti
        </button>
      </div>
    </div>
  );
}
