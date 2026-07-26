"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["/", "Overview"],
  ["/ceo", "CEO"],
  ["/goals", "Goals"],
  ["/approvals", "Approvals"],
  ["/agents", "Agents"],
  ["/audit", "Audit"],
  ["/status", "Build status"],
] as const;

export function Nav() {
  const pathname = usePathname();
  return (
    <>
      {LINKS.map(([href, text]) => (
        <Link
          key={href}
          href={href}
          aria-current={pathname === href ? "page" : undefined}
        >
          {text}
        </Link>
      ))}
    </>
  );
}
