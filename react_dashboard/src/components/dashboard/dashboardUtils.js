export const OVERVIEW_RANGES = [
    { value: "7d", label: "Last 7 days", days: 7 },
    { value: "28d", label: "Last 28 days", days: 28 },
    { value: "90d", label: "Last 90 days", days: 90 },
];

export const OVERVIEW_LIMIT_STEP = 10;
export const OVERVIEW_LIMIT_MAX = 50;
export const OVERVIEW_LIMIT_DEFAULT = 10;
export const LATEST_VIDEOS_PAGE_SIZE = 5;

export const formatNumber = (n) => {
    if (n == null) return "-";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toString();
};

export const formatCurrency = (value) => {
    if (value == null) return "-";
    const num = Number(value);
    if (Number.isNaN(num)) return "-";
    return `$${num.toFixed(2)}`;
};

export const formatRate = (value, digits = 1) => {
    if (value == null) return "-";
    const num = Number(value);
    if (!Number.isFinite(num)) return "-";
    return `${num.toFixed(digits)}%`;
};

export const formatDuration = (seconds) => {
    if (seconds == null) return "-";
    const total = Math.max(0, Math.round(Number(seconds)));
    if (!Number.isFinite(total)) return "-";
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    if (mins <= 0) return `${secs}s`;
    return `${mins}m ${secs.toString().padStart(2, "0")}s`;
};

export const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const year = d.getFullYear().toString().slice(-2);

    return `${day}/${month}/${year}`;
};

export const formatDateFull = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const year = d.getFullYear().toString();

    return `${day}-${month}-${year}`;
};

export const formatDateMonth = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");

    return `${day}/${month}`;
};
