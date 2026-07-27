import type { NextRequest } from "next/server";

import { refreshAndAuthorize } from "@/lib/supabase/middleware";

export function middleware(request: NextRequest) {
  return refreshAndAuthorize(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
