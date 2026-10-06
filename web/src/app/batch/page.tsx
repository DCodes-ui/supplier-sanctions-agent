"use client";

import { FormEvent, useState } from "react";
import { DecisionView } from "@/components/decision";
import { ApiError, api } from "@/lib/api";
import type { Screening } from "@/lib/types";

export default function BatchPage() {
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<Screening[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setPending(true);
    setError("");
    setRows([]);
    const body = new FormData();
    body.set("file", file);
    try {
      setRows(await api<Screening[]>("/batch", { method: "POST", body }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Batch failed.");
    } finally {
      setPending(false);
    }
  }

  const counts = rows.reduce<Record<string, number>>((total, row) => {
    total[row.decision.status] = (total[row.decision.status] ?? 0) + 1;
    return total;
  }, {});

  return (
    <>
      <h1 className="text-2xl font-semibold">Batch</h1>
      <form onSubmit={onSubmit} className="grid gap-3">
        <input
          required
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button
          type="submit"
          disabled={pending}
          className="w-fit rounded bg-zinc-950 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {pending ? "Screening…" : "Upload CSV"}
        </button>
      </form>
      <p className="text-sm text-zinc-600">
        Columns: supplier_id, name, country, registration_number
      </p>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {rows.length > 0 ? (
        <>
          <p className="text-sm">
            {rows.length} screened
            {Object.entries(counts).map(([status, count]) => ` · ${status} ${count}`)}
          </p>
          {rows.map((row) => (
            <article key={row.id} className="grid gap-2">
              <h2 className="font-medium">
                {row.query_name} · {row.query_country}
              </h2>
              <DecisionView decision={row.decision} />
            </article>
          ))}
        </>
      ) : null}
    </>
  );
}
