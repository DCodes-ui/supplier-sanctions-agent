"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { Datasets } from "@/lib/types";

export default function DatasetsPage() {
  const [data, setData] = useState<Datasets | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Datasets>("/datasets")
      .then(setData)
      .catch((caught) => {
        setError(caught instanceof ApiError ? caught.message : "Could not load datasets.");
      });
  }, []);

  return (
    <>
      <h1 className="text-2xl font-semibold">Datasets</h1>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {data && !data.active ? (
        <p className="text-sm">Lists are not loaded yet. Run ingest, then refresh this page.</p>
      ) : null}
      {data?.active ? (
        <>
          <p className="text-sm text-zinc-600">Snapshot {data.snapshot_id}</p>
          <ul className="grid gap-3">
            {data.sources.map((source) => (
              <li key={source.source} className="rounded border border-zinc-200 p-3 text-sm">
                <p className="font-medium">{source.source}</p>
                <p>{source.record_count ?? 0} records</p>
                <p className="text-zinc-600">{source.fetched_at}</p>
                {source.error ? <p className="text-red-700">{source.error}</p> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}
