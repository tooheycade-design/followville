import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export function publicConfiguration(): { url: string; key: string } {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase Auth requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.",
    );
  }
  return { url, key };
}

export function companyOsSiteUrl(): URL {
  const configured = process.env.COMPANY_OS_SITE_URL?.trim();
  const vercelHost =
    process.env.VERCEL_PROJECT_PRODUCTION_URL?.trim() ??
    process.env.VERCEL_URL?.trim();
  const value =
    configured ??
    (vercelHost ? `https://${vercelHost}` : "http://localhost:4100");
  const url = new URL(value);

  if (url.protocol !== "https:" && url.hostname !== "localhost") {
    throw new Error("COMPANY_OS_SITE_URL must use HTTPS outside localhost.");
  }
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url;
}

/** A request-scoped client carrying only the caller's cookie session. */
export async function createAuthClient() {
  const { url, key } = publicConfiguration();
  const cookieStore = await cookies();

  return createServerClient(url, key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options);
          });
        } catch {
          // Server Components cannot write cookies. Middleware refreshes them.
        }
      },
    },
  });
}
