export function appFor(action: string, tab: string) {
  if (tab === "Emails") return "Email";
  if (tab === "Map") return "GPS / Location";
  if (action.toLowerCase().includes("debit")) return "UPI / Bank";
  return "WhatsApp";
}

export function pretty(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatTime(value?: string | null) {
  if (!value) return "Unknown time";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}
