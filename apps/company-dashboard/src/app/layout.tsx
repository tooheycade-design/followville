import type { Metadata } from "next";

import { currentOwner } from "@/lib/auth";
import { companyRepository } from "@/lib/state";
import { logoutAction } from "./actions";
import { Nav } from "./nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Followville Company OS",
  description:
    "Private owner dashboard for Followville's owner-gated AI workers.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const owner = await currentOwner();

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
              Automated workers active · owner-gated production · $0 metered
              API spend (subscription usage not measured) ·{" "}
              {companyRepository().backend === "supabase"
                ? "shared database"
                : "local store"}
            </span>
          </header>
          <div className="nav">
            <Nav />
            {owner === null ? (
              <span className="identity">Not signed in</span>
            ) : (
              <form action={logoutAction} className="identity">
                <span>{owner.email}</span>
                <button type="submit" className="quiet">
                  Sign out
                </button>
              </form>
            )}
          </div>
          <main>{children}</main>
          <footer className="dev-note">
            Identity is validated by Supabase Auth and active Company OS owner
            membership. Nothing on this dashboard can merge, deploy, publish,
            spend, or touch the live town.
          </footer>
        </div>
      </body>
    </html>
  );
}
