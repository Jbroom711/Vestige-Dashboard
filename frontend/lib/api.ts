/**
 * Typed fetch wrapper for the Vestige backend.
 *
 * Responsibilities:
 *   - Attach the Supabase access token as a bearer credential
 *   - snake_case <-> camelCase conversion at the boundary
 *   - Normalize HTTP errors into ApiError
 *
 * Components should import helpers from here — never call fetch() directly.
 */

import { createSupabaseBrowserClient } from "@/lib/supabase/browser";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8007";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------- case conversion ---------------------------------------------
function snakeToCamel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}
function camelToSnake(s: string): string {
  return s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
}

type Json = string | number | boolean | null | Json[] | { [k: string]: Json };

function convertKeys(value: Json, conv: (k: string) => string): Json {
  if (Array.isArray(value)) return value.map((v) => convertKeys(v, conv));
  if (value && typeof value === "object") {
    const out: { [k: string]: Json } = {};
    for (const [k, v] of Object.entries(value)) out[conv(k)] = convertKeys(v, conv);
    return out;
  }
  return value;
}

// ---------- core fetcher -------------------------------------------------
type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface ApiCallOptions {
  body?: unknown;
  searchParams?: Record<string, string | number | boolean | undefined>;
}

async function getAccessToken(): Promise<string | null> {
  const supabase = createSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function apiCall<TResp>(
  method: Method,
  path: string,
  options: ApiCallOptions = {},
): Promise<TResp> {
  const token = await getAccessToken();

  const url = new URL(path.replace(/^\//, ""), API_URL + "/");
  if (options.searchParams) {
    for (const [k, v] of Object.entries(options.searchParams)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";

  const body =
    options.body !== undefined
      ? JSON.stringify(convertKeys(options.body as Json, camelToSnake))
      : undefined;

  const res = await fetch(url.toString(), { method, headers, body });
  const raw = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      (raw && typeof raw === "object" && "detail" in raw
        ? String((raw as { detail: unknown }).detail)
        : null) ?? `${method} ${path} failed (${res.status})`;
    throw new ApiError(res.status, message, raw);
  }

  return (raw === null ? null : convertKeys(raw, snakeToCamel)) as TResp;
}

// ---------- public helpers ----------------------------------------------
export const api = {
  get: <T>(path: string, searchParams?: ApiCallOptions["searchParams"]) =>
    apiCall<T>("GET", path, { searchParams }),
  post: <T>(path: string, body?: unknown) => apiCall<T>("POST", path, { body }),
  patch: <T>(path: string, body?: unknown) => apiCall<T>("PATCH", path, { body }),
  delete: <T>(path: string) => apiCall<T>("DELETE", path),
};
