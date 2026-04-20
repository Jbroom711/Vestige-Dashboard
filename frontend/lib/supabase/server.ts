import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Supabase client for Server Components, Route Handlers, and Server Actions.
 *
 * Note on Next 16: `cookies()` is async. Server Components are allowed to
 * *read* cookies but not to *set* them — setting must happen in a Route
 * Handler, Server Action, or the root proxy.ts. This client silently swallows
 * the "can't set cookies" error when called from a Server Component; actual
 * cookie refresh writes happen in proxy.ts.
 */
export async function createSupabaseServerClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            for (const { name, value, options } of cookiesToSet) {
              cookieStore.set(name, value, options);
            }
          } catch {
            // Called from a Server Component — cookie writes are rejected.
            // proxy.ts handles refresh writes for these requests.
          }
        },
      },
    },
  );
}
