"use client";

import { useEffect, useState } from "react";
import { DecisionView } from "@/components/decision";
import { ApiError, api } from "@/lib/api";
import type { Screening } from "@/lib/types";

export default function HistoryPage() {
  const [rows, setRows] = useState<Screening[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api<Screening[]>("/screenings")
      .then(setRows)
      .catch((caught) => {
        setError(caught instanceof ApiError ? caught.message : "Could not load history.");
      })
      .finally(() => setLoaded(true));
  }, []);

  return (
    <>
      <h1 className="text-2xl font-semibold">History</h1>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {!error && loaded && rows.length === 0 ? (
        <p className="text-sm text-zinc-600">No screenings yet.</p>
      ) : null}
      {rows.map((row) => (
        <article key={row.id} className="grid gap-2">
          <h2 className="font-medium">
            {row.query_name} · {row.query_country}
          </h2>
          <DecisionView decision={row.decision} adjudication={row.adjudication} />
        </article>
      ))}
    </>
  );
}
