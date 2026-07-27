import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

function redirectWithSession(url: URL, sessionResponse: NextResponse) {
  const redirect = NextResponse.redirect(url);
  sessionResponse.cookies.getAll().forEach((cookie) => {
    redirect.cookies.set(cookie);
  });
  for (const name of ["expires", "pragma", "vary"]) {
    const value = sessionResponse.headers.get(name);
    if (value !== null) {
      redirect.headers.set(name, value);
    }
  }
  redirect.headers.set("Cache-Control", "private, no-store");
  return redirect;
}

export async function refreshAndAuthorize(request: NextRequest) {
  let response = NextResponse.next({ request });
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    return NextResponse.json(
      { error: "Company OS authentication is not configured." },
      { status: 503 },
    );
  }

  const client = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => {
          request.cookies.set(name, value);
        });
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => {
          response.cookies.set(name, value, options);
        });
        Object.entries(headers).forEach(([name, value]) => {
          response.headers.set(name, value);
        });
      },
    },
  });

  const { data: claimsData } = await client.auth.getClaims();
  const subject = claimsData?.claims?.sub;
  const publicRoute =
    request.nextUrl.pathname.startsWith("/login") ||
    request.nextUrl.pathname.startsWith("/auth") ||
    request.nextUrl.pathname.startsWith("/forgot-password") ||
    request.nextUrl.pathname.startsWith("/reset-password");

  if (typeof subject !== "string") {
    if (publicRoute) {
      return response;
    }
    const login = request.nextUrl.clone();
    login.pathname = "/login";
    login.searchParams.set("next", request.nextUrl.pathname);
    return redirectWithSession(login, response);
  }

  const { data: membership } = await client.rpc("company_os_my_membership");
  const activeOwner =
    membership !== null &&
    typeof membership === "object" &&
    (membership as MembershipRow).userId === subject &&
    (membership as MembershipRow).role === "owner";

  if (!activeOwner && !request.nextUrl.pathname.startsWith("/unauthorized")) {
    const denied = request.nextUrl.clone();
    denied.pathname = "/unauthorized";
    denied.search = "";
    return redirectWithSession(denied, response);
  }
  const recoveryRoute = request.nextUrl.pathname.startsWith("/reset-password");
  if (activeOwner && publicRoute && !recoveryRoute) {
    const dashboard = request.nextUrl.clone();
    dashboard.pathname = "/";
    dashboard.search = "";
    return redirectWithSession(dashboard, response);
  }

  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

interface MembershipRow {
  userId?: unknown;
  role?: unknown;
}
