export type Decision = {
  status: "clear" | "review" | "likely_hit";
  matched_entity: {
    name: string;
    list: string;
    programme: string;
    source_record_id: string;
  } | null;
  match_confidence: number;
  evidence: { source: string; url: string; snippet: string; kind: string }[];
  recommended_action: string;
  snapshot_id: string;
  decision_basis: string;
  rationale: string;
};

export type Screening = {
  id: string;
  created_at: string;
  supplier_id: string | null;
  query_name: string;
  query_country: string;
  query_registration_number: string | null;
  decision: Decision;
  adjudication?: string;
};

export type DatasetSource = {
  source: string;
  sha256: string;
  record_count: number | null;
  records_skipped: number | null;
  error: string | null;
  fetched_at: string;
};

export type Datasets = {
  snapshot_id: string | null;
  active: boolean;
  sources: DatasetSource[];
};
