import type { Metadata } from "next";
import { cookies } from "next/headers";

import { OWNER_COOKIE, OWNERS, ownerById } from "@/lib/config";
import { companyRepository } from "@/lib/state";
import { switchOwnerAction } from "./actions";
import { Nav } from "./nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Followville Company OS",
  description:
    "Private owner dashboard for the Followville AI company. Simulation-only.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const currentOwner = ownerById(cookieStore.get(OWNER_COOKIE)?.value);

  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="masthead">
            <h1>
              Followville <span>Company OS</span>
            </h1>
            {/*
              "$0 metered" rather than "$0 budget". The ledger records no
              incremental API spend because the work runs on existing Codex and
              Claude subscriptions, which it does not measure — not because the
              work is free. Saying "$0 budget" would eventually make the
              dashboard's cost picture a comfortable fiction.
            */}
            <span
              className="sim-flag"
              title="Model work runs on existing Codex and Claude subscriptions. Subscription usage is not metered by this ledger, so it is not included here."
            >
              Simulation only · $0 metered API spend (subscription usage not
              measured) ·{" "}
              {companyRepository().backend === "supabase"
                ? "shared database"
                : "local store"}
            </span>
          </header>
          <div className="nav">
            <Nav />
            <form action={switchOwnerAction} className="identity">
              <span>Acting as</span>
              <select name="owner" defaultValue={currentOwner.id}>
                {OWNERS.map((owner) => (
                  <option key={owner.id} value={owner.id}>
                    {owner.name}
                  </option>
                ))}
              </select>
              <button type="submit" className="quiet">
                Switch
              </button>
            </form>
          </div>
          <main>{children}</main>
          <footer className="dev-note">
            Local development identity picker — real owner sign-in arrives with
            the separate development Supabase project (requires human setup).
            Nothing on this dashboard can merge, deploy, publish, spend, or
            touch the live town.
          </footer>
        </div>
      </body>
    </html>
  );
}
