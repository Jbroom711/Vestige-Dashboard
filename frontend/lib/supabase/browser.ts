import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase client for use inside Client Components. Reads session cookies via
 * the browser's document.cookie; token refreshes flow back through the same
 * cookie store so server and client stay in sync.
 */
export function createSupabaseBrowserClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
