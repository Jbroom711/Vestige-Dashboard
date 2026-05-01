/**
 * Server-side counterpart to lib/api.ts.
 *
 * Use from Server Components and Route Handlers. Pulls the Supabase session
 * via the per-request server client, attaches the access token as a Bearer
 * credential, and forwards the call to the FastAPI backend. Same
 * snake_case<->camelCase conversion at the boundary as the browser wrapper.
 *
 * Components rendering on the server should always import from here, not
 * from lib/api.ts (which uses the browser supabase client and won't work
 * during SSR).
 */

import "server-only";

import { createSupabaseServerClient } from "@/lib/supabase/server";

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

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface ApiCallOptions {
  body?: unknown;
  searchParams?: Record<string, string | number | boolean | undefined>;
}

async function apiServerCall<TResp>(
  method: Method,
  path: string,
  options: ApiCallOptions = {},
): Promise<TResp> {
  const supabase = await createSupabaseServerClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const token = session?.access_token;

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

  // Default fetch in Next 16 with cacheComponents off is uncached — perfect
  // for live financial data.
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

export const apiServer = {
  get: <T>(path: string, searchParams?: ApiCallOptions["searchParams"]) =>
    apiServerCall<T>("GET", path, { searchParams }),
  post: <T>(path: string, body?: unknown) => apiServerCall<T>("POST", path, { body }),
  patch: <T>(path: string, body?: unknown) => apiServerCall<T>("PATCH", path, { body }),
  delete: <T>(path: string) => apiServerCall<T>("DELETE", path),
};
