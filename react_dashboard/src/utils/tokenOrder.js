const normalizeTokenOrderValue = (value) =>
  String(value || "")
    .replace(/\.pickle$/i, "")
    .trim()
    .toLowerCase();

export const getStoredTokenOrder = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem("tokens.order") || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeTokenOrderValue).filter(Boolean);
  } catch {
    return [];
  }
};

export const sortByStoredTokenOrder = (items, getValue) => {
  const order = getStoredTokenOrder();
  if (!Array.isArray(items) || !items.length || !order.length) {
    return Array.isArray(items) ? items : [];
  }

  const orderSet = new Set(order);
  const byId = new Map(
    items.map((item) => [normalizeTokenOrderValue(getValue(item)), item])
  );
  const ordered = order.map((value) => byId.get(value)).filter(Boolean);
  const remaining = items.filter(
    (item) => !orderSet.has(normalizeTokenOrderValue(getValue(item)))
  );
  return [...ordered, ...remaining];
};
