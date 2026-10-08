"use client";

import { useEffect, useState } from "react";
import { statusTone } from "@/components/decision";
import { ApiError, api } from "@/lib/api";
import type { Datasets, Decision } from "@/lib/types";

const labels: { status: Decision["status"]; text: string }[] = [
  {
    status: "clear",
    text: "No listed name scored 0.72 or higher, and the country is not on the elevated-risk list. Proceed and record the screening.",
  },
  {
    status: "review",
    text: "A possible match is not strong enough to block, the name is shared by 8 or more listed people, the country conflicts, or the country is KP, IR, SY, or CU with no list hit. Do not onboard or pay until an analyst confirms.",
  },
  {
    status: "likely_hit",
    text: "The registration number matches one listed record, or the name scores at least 0.90 and a second fact supports it. Stop. Do not transact.",
  },
];

export default function InfoPage() {
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
      <h1 className="text-2xl font-semibold">Info</h1>
      <section className="grid gap-4">
        <h2 className="text-sm font-medium text-zinc-600">What the labels mean</h2>
        <ul className="grid gap-3">
          {labels.map((label) => (
            <li key={label.status} className="grid gap-2">
              <p className={`w-fit rounded px-2 py-1 text-sm font-semibold ${statusTone[label.status]}`}>
                {label.status}
              </p>
              <p className="text-sm leading-6">{label.text}</p>
            </li>
          ))}
        </ul>
        <div className="grid gap-2 text-sm leading-6">
          <p className="font-medium">Score</p>
          <p>
            A sanctions list is a set of names. The supplier you type is either an exact copy of one of those names, or it is not.
          </p>
          <p>1.00 means the same name, or the same registration number.</p>
          <p>
            Most checks are not exact. The name on the invoice is often written differently from the name on the list: an extra legal form (UAB, Ltd), a missing middle word, a spelling variant, or an alias. The score measures that difference, from 0 to 1.
          </p>
          <p>
            0.90 means the typed name is very similar to one name on the list. At 0.90 or above, the result can be a likely hit when a second fact agrees, such as the country. From 0.72 up to 0.90 the result stays review. Below 0.72 the name is dropped.
          </p>
        </div>
      </section>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {data && !data.active ? (
        <p className="text-sm">Lists are not loaded yet.</p>
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
