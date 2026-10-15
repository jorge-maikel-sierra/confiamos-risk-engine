export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null) return "N/A";
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatRatio(value: number | null | undefined, suffix = "x"): string {
  if (value == null) return "N/A";
  return `${value.toFixed(2)}${suffix}`;
}

export function formatDate(isoString?: string): string {
  if (!isoString) return "Fecha no registrada";
  try {
    return new Intl.DateTimeFormat("es-CO", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(isoString));
  } catch {
    return isoString;
  }
}
