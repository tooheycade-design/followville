import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

function publicConfiguration(): { url: string; key: string } {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase Auth requires SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY.",
    );
  }
  return { url, key };
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
