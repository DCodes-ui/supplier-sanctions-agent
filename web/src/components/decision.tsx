import type { Decision } from "@/lib/types";

export const statusTone: Record<Decision["status"], string> = {
  clear: "bg-emerald-100 text-emerald-950",
  review: "bg-amber-100 text-amber-950",
  likely_hit: "bg-red-100 text-red-950",
};

export function DecisionView({
  decision,
  adjudication,
}: {
  decision: Decision;
  adjudication?: string;
}) {
  const matched = decision.matched_entity;
  return (
    <section className="grid gap-4 rounded-lg border border-zinc-200 p-4">
      {adjudication === "fallback" ? (
        <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-950">
          The model call failed. This result was checked by the score rules, not by Grok.
        </p>
      ) : null}
      <p className={`w-fit rounded px-2 py-1 text-sm font-semibold ${statusTone[decision.status]}`}>
        {decision.status}
      </p>
      <p>{decision.recommended_action}</p>
      <dl className="grid gap-2 text-sm">
        <div>
          <dt className="text-zinc-500">Confidence</dt>
          <dd>{decision.match_confidence.toFixed(2)}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Basis</dt>
          <dd>{decision.decision_basis}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Snapshot</dt>
          <dd>{decision.snapshot_id}</dd>
        </div>
        {matched ? (
          <div>
            <dt className="text-zinc-500">Match</dt>
            <dd>
              {matched.name}
              <span className="block text-zinc-600">
                {matched.list}
                {matched.programme ? ` · ${matched.programme}` : ""}
              </span>
            </dd>
          </div>
        ) : null}
      </dl>
      {decision.rationale ? <p className="text-sm leading-6">{decision.rationale}</p> : null}
      {decision.evidence.length > 0 ? (
        <ul className="grid gap-2 text-sm">
          {decision.evidence.map((item) => (
            <li key={`${item.kind}-${item.source}-${item.url}`}>
              {item.url ? (
                <a className="underline" href={item.url}>
                  {item.source}
                </a>
              ) : (
                item.source
              )}
              {item.snippet ? <span className="block text-zinc-600">{item.snippet}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
