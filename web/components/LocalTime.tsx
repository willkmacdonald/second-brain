"use client";

import { useEffect, useState } from "react";

type Mode = "full" | "time";

export function LocalTime({ iso, mode = "full" }: { iso: string; mode?: Mode }) {
  const [rendered, setRendered] = useState<string>("");

  useEffect(() => {
    const d = new Date(iso);
    setRendered(mode === "time" ? d.toLocaleTimeString() : d.toLocaleString());
  }, [iso, mode]);

  // Suppress SSR hydration mismatch on the text content; initial empty render is replaced on mount.
  return <span suppressHydrationWarning>{rendered}</span>;
}
