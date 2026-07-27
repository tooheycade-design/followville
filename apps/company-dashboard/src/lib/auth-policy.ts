export function safeReturnPath(value: FormDataEntryValue | string | null): string {
  const requested = String(value ?? "/");
  let decoded: string;
  try {
    decoded = decodeURIComponent(requested);
  } catch {
    return "/";
  }
  return requested.startsWith("/") &&
    decoded.startsWith("/") &&
    !decoded.startsWith("//") &&
    !decoded.includes("\\")
    ? requested
    : "/";
}
