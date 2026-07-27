"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function LiveRefresh() {
  const router = useRouter();
  const [updatedAt, setUpdatedAt] = useState<string>("");

  useEffect(() => {
    setUpdatedAt(new Date().toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    }));
    const timer = window.setInterval(() => {
      router.refresh();
      setUpdatedAt(new Date().toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      }));
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [router]);

  return (
    <div className="live-indicator" aria-live="polite">
      <span aria-hidden="true" />
      Live
      {updatedAt !== "" && <time>{updatedAt}</time>}
    </div>
  );
}
