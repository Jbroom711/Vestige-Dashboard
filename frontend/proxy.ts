import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Next.js 16 replaces middleware.ts with proxy.ts (same runtime position:
 * before any route handler or rendering).
 *
 * Responsibilities here:
 *   1. Refresh the Supabase session on every request (so server-rendered
 *      pages see a fresh user).
 *   2. Gate route groups: send unauthenticated users to /login when they
 *      hit (app) routes; send logged-in users away from (auth) routes;
 *      route pending-approval users to /pending.
 *
 * Approval/role enforcement happens server-side on the backend; this is
 * just the first line of UX defense.
 */

const PUBLIC_PATHS = ["/login", "/signup", "/auth/callback"];
const PENDING_PATH = "/pending";

export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          for (const { name, value } of cookiesToSet) {
            request.cookies.set(name, value);
          }
          response = NextResponse.next({ request });
          for (const { name, value, options } of cookiesToSet) {
            response.cookies.set(name, value, options);
          }
        },
      },
    },
  );

  // Must call getUser() (verified) before any redirect so token refreshes
  // get written back via setAll.
  const { data: { user } } = await supabase.auth.getUser();

  const { pathname } = request.nextUrl;
  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  if (!user && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }

  if (user && (pathname === "/login" || pathname === "/signup")) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    return NextResponse.redirect(url);
  }

  // Pending-approval UX. Source of truth is profiles.status — we check it
  // cheaply here and the backend enforces it.
  if (user && pathname !== PENDING_PATH && !isPublic) {
    const { data: profile } = await supabase
      .from("profiles")
      .select("status")
      .eq("id", user.id)
      .maybeSingle();

    if (profile?.status === "pending") {
      const url = request.nextUrl.clone();
      url.pathname = PENDING_PATH;
      return NextResponse.redirect(url);
    }
  }

  return response;
}

export const config = {
  // Run on every route except static assets and the Next.js internals
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|manifest.webmanifest|sw.js|icons|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
