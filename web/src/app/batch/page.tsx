"use client";

import { FormEvent, useRef, useState } from "react";
import { DecisionView } from "@/components/decision";
import { ApiError, api } from "@/lib/api";
import type { Screening } from "@/lib/types";

const LISTS = [
  { id: "eu_fsf", label: "EU Financial Sanctions" },
  { id: "ofac_sdn", label: "OFAC SDN" },
  { id: "opensanctions", label: "OpenSanctions" },
];

export default function BatchPage() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [source, setSource] = useState(LISTS[0].id);
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
    body.set("source", source);
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
        <label className="grid gap-1 text-sm">
          List
          <select
            value={source}
            onChange={(event) => setSource(event.target.value)}
            className="rounded border border-zinc-300 bg-white px-2 py-1 text-zinc-950"
          >
            {LISTS.map((list) => (
              <option key={list.id} value={list.id}>
                {list.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-3 text-sm">
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="rounded border border-zinc-300 bg-white px-3 py-1.5 text-zinc-950"
          >
            Choose CSV
          </button>
          <span>{file ? file.name : "No file selected"}</span>
          <input
            ref={fileInput}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        <button
          type="submit"
          disabled={pending || !file}
          className="w-fit rounded border border-white bg-zinc-950 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {pending ? "Screening…" : "Screen batch"}
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
              <DecisionView decision={row.decision} adjudication={row.adjudication} />
            </article>
          ))}
        </>
      ) : null}
    </>
  );
}
