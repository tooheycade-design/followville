export function formatUsdMicros(micros: number): string {
  return `$${(micros / 1_000_000).toFixed(2)}`;
}

export function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function label(value: string): string {
  return value.replaceAll("_", " ");
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}
