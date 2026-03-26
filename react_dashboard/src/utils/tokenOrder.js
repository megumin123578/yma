const normalizeTokenOrderValue = (value) =>
  String(value || "")
    .replace(/\.pickle$/i, "")
    .trim()
    .toLowerCase();

const HIDDEN_TOKEN_STORAGE_KEY = "tokens.hidden";

export const getStoredTokenOrder = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem("tokens.order") || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.map(normalizeTokenOrderValue).filter(Boolean);
  } catch {
    return [];
  }
};

export const setStoredHiddenTokens = (items) => {
  try {
    const hidden = (Array.isArray(items) ? items : [])
      .filter((item) => typeof item === "object" && item?.hidden)
      .map((item) => normalizeTokenOrderValue(item?.name || item?.value || item))
      .filter(Boolean);
    localStorage.setItem(HIDDEN_TOKEN_STORAGE_KEY, JSON.stringify(hidden));
  } catch {
    // ignore storage errors
  }
};

export const getStoredHiddenTokens = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(HIDDEN_TOKEN_STORAGE_KEY) || "[]");
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.map(normalizeTokenOrderValue).filter(Boolean));
  } catch {
    return new Set();
  }
};

export const sortByStoredTokenOrder = (items, getValue) => {
  const order = getStoredTokenOrder();
  const hidden = getStoredHiddenTokens();
  if (!Array.isArray(items) || !items.length) return [];

  let sorted = items;
  if (order.length) {
    const orderSet = new Set(order);
    const byId = new Map(
      items.map((item) => [normalizeTokenOrderValue(getValue(item)), item])
    );
    const ordered = order.map((value) => byId.get(value)).filter(Boolean);
    const remaining = items.filter(
      (item) => !orderSet.has(normalizeTokenOrderValue(getValue(item)))
    );
    sorted = [...ordered, ...remaining];
  }

  if (!hidden.size) return sorted;

  const visible = [];
  const hiddenItems = [];
  sorted.forEach((item) => {
    const key = normalizeTokenOrderValue(getValue(item));
    if (hidden.has(key)) {
      hiddenItems.push(item);
    } else {
      visible.push(item);
    }
  });
  return [...visible, ...hiddenItems];
};
