"use client";

import { FormEvent, useState } from "react";
import { DecisionView } from "@/components/decision";
import { ApiError, api } from "@/lib/api";
import type { Screening } from "@/lib/types";

export default function ScreenPage() {
  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [result, setResult] = useState<Screening | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    setResult(null);
    try {
      const body = await api<Screening>("/screen", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          name,
          country,
          registration_number: registrationNumber || null,
        }),
      });
      setResult(body);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Screening failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold">Screen a supplier</h1>
      <form onSubmit={onSubmit} className="grid gap-3">
        <label className="grid gap-1 text-sm">
          Name
          <input
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="rounded border border-zinc-300 px-2 py-1"
          />
        </label>
        <label className="grid gap-1 text-sm">
          Country
          <input
            required
            value={country}
            onChange={(event) => setCountry(event.target.value)}
            className="rounded border border-zinc-300 px-2 py-1"
            placeholder="IQ"
          />
        </label>
        <label className="grid gap-1 text-sm">
          Registration number
          <input
            value={registrationNumber}
            onChange={(event) => setRegistrationNumber(event.target.value)}
            className="rounded border border-zinc-300 px-2 py-1"
          />
        </label>
        <button
          type="submit"
          disabled={pending}
          className="w-fit rounded border border-white bg-zinc-950 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {pending ? "Screening…" : "Screen"}
        </button>
      </form>
      {error ? <p className="text-sm text-red-700">{error}</p> : null}
      {result ? <DecisionView decision={result.decision} adjudication={result.adjudication} /> : null}
    </>
  );
}
