import type {
  CompareResponse,
  Limits,
  ModelInfo,
  SimulateRequest,
  SimulateResponse,
  TokenizeResponse,
  TokenizerInfo,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Turn the server's error body into one readable sentence. */
export function formatDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const where = Array.isArray(first.loc) ? first.loc.slice(1).join(".") : "";
    return where ? `${where}: ${first.msg ?? "invalid"}` : (first.msg ?? fallback);
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      message = formatDetail(body.detail, message);
    } catch {
      /* the body was not JSON: keep the status text */
    }
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export const getTokenizers = (signal?: AbortSignal) =>
  request<TokenizerInfo[]>("/api/tokenizers", { signal });

export const getLimits = (signal?: AbortSignal) => request<Limits>("/api/limits", { signal });

export const tokenize = (text: string, tokenizer: string, signal?: AbortSignal) =>
  request<TokenizeResponse>("/api/tokenize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, tokenizer }),
    signal,
  });

export const compare = (text: string, tokenizers: string[], signal?: AbortSignal) =>
  request<CompareResponse>("/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, tokenizers }),
    signal,
  });

export const getModels = (signal?: AbortSignal) => request<ModelInfo[]>("/api/models", { signal });

export const simulate = (req: SimulateRequest, signal?: AbortSignal) =>
  request<SimulateResponse>("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
    signal,
  });
