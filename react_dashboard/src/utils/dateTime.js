const UTC_SUFFIX_PATTERN = /(z|[+-]\d{2}:\d{2})$/i;

export const parseApiDateTime = (value) => {
  if (!value) return null;

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = String(value).trim();
  if (!raw) return null;

  const isoLikeValue = raw.includes("T") || raw.includes(" ") ? raw.replace(" ", "T") : raw;
  const normalizedValue = UTC_SUFFIX_PATTERN.test(isoLikeValue)
    ? isoLikeValue
    : `${isoLikeValue}Z`;

  const parsed = new Date(normalizedValue);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed;
  }

  const fallback = new Date(raw);
  return Number.isNaN(fallback.getTime()) ? null : fallback;
};

export const formatDateTimeInSaigon = (value, fallback = "-") => {
  const parsed = parseApiDateTime(value);
  if (!parsed) return fallback;
  return parsed.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
};

export const formatShortDateTimeInSaigon = (value, fallback = "") => {
  const parsed = parseApiDateTime(value);
  if (!parsed) return fallback;
  return parsed.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};
