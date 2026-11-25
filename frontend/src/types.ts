// These types mirror api/schemas.py. If you change one side, change the other.
export interface Token {
  id: number;
  text: string;
  piece: string;
  start: number; // UTF-8 byte offset, inclusive
  end: number; // UTF-8 byte offset, exclusive
}

export interface TokenizeResponse {
  tokenizer: string;
  count: number;
  chars: number;
  bytes: number;
  chars_per_token: number | null;
  tokens: Token[]; // at most 2,000; `count` is always the full number
  truncated: boolean;
}

export interface TokenizerInfo {
  name: string;
  family: string;
  algorithm: string;
  exact: boolean; // false = an estimate, not a real tokenizer
  has_tokens: boolean; // false = only a count exists, there is no token list
}

/** One row of /api/compare. A tokenizer that failed has `error` set and no count. */
export interface CompareResult {
  name: string;
  family: string;
  algorithm: string;
  exact: boolean;
  has_tokens: boolean;
  count: number | null;
  chars_per_token: number | null;
  tokens: Token[]; // at most 1,000; `count` is always the full number
  truncated: boolean;
  error: string | null;
}

export interface CompareResponse {
  chars: number;
  bytes: number;
  results: CompareResult[];
}

export interface Limits {
  max_text_chars: number;
}

export interface ModelInfo {
  id: string;
  display_name: string;
  tokenizer: string;
  context_window: number;
  max_output_tokens: number | null;
  source_url: string;
  last_verified: string;
}

// ---- /api/simulate ----
export type Role = "system" | "user" | "assistant";
export type Strategy = "error" | "drop_oldest" | "truncate_start" | "truncate_end";

export interface SimMessage {
  role: Role;
  text: string;
}

export interface SimMessageResult {
  index: number;
  role: Role;
  chars: number;
  tokens: number; // the message's own tokens, without the per-message overhead
  status: "kept" | "partial" | "dropped";
  kept_tokens: number;
  kept_chars: [number, number] | null; // [start, end) in characters, only for "partial"
}

export interface SimulateRequest {
  model: string;
  messages: SimMessage[];
  strategy: Strategy;
  context_window: number | null;
  reserve_output: number;
  per_message_overhead: number;
}

export interface SimulateResponse {
  model: string;
  tokenizer: string;
  exact: boolean;
  strategy: Strategy;
  context_window: number;
  reserve_output: number;
  budget: number;
  per_message_overhead: number;
  total_tokens: number;
  used_tokens: number;
  overflow_tokens: number;
  fits: boolean;
  cannot_fit: boolean;
  nothing_fits: boolean;
  messages: SimMessageResult[];
}
