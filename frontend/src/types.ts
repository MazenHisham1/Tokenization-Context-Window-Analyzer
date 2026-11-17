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
  tokens: Token[];
}

export interface TokenizerInfo {
  name: string;
  family: string;
  algorithm: string;
  exact: boolean;
}

export interface Limits {
  max_text_chars: number;
}
