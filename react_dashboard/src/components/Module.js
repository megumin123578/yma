// Module.js
import * as React from "react";
import { Box, Typography } from "@mui/material";
import api from "../services/api";

// ===== Helpers =====
export const n = (v) => (isNaN(+v) ? 0 : +v);
export const pad2 = (x) => String(x).padStart(2, "0");
export const toYMD = (d) =>
  `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
export const formatNumber = (v) =>
  n(v).toLocaleString(undefined, { maximumFractionDigits: 0 });
export const formatSeconds = (sec) => {
  const s = Math.floor(n(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}h ${m}m ${r}s`;
  if (m > 0) return `${m}m ${r}s`;
  return `${r}s`;
};

// ===== Metrics =====
export const METRICS = {
  views: { label: "Views", valueOf: (d) => n(d.views) },
  estimatedMinutesWatched: {
    label: "Estimated Minutes",
    valueOf: (d) => n(d.estimatedMinutesWatched),
  },
  averageViewDuration: {
    label: "Avg View Duration (s)",
    valueOf: (d) => n(d.averageViewDuration),
  },
  averageViewPercentage: {
    label: "Avg View %",
    valueOf: (d) => n(d.averageViewPercentage),
  },
  engagedViews: { label: "Engaged Views", valueOf: (d) => n(d.engagedViews) },
};

export const METRIC_OPTIONS = [
  { value: "views", label: METRICS.views.label },
  { value: "estimatedMinutesWatched", label: METRICS.estimatedMinutesWatched.label },
  { value: "averageViewDuration", label: METRICS.averageViewDuration.label },
  { value: "averageViewPercentage", label: METRICS.averageViewPercentage.label },
  { value: "engagedViews", label: METRICS.engagedViews.label },
];

// ===== Periods =====
export const PERIOD_OPTIONS = [
  { value: "last7", label: "Last 7 days" },
  { value: "last28", label: "Last 28 days" },
  { value: "last90", label: "Last 90 days" },
  { value: "last365", label: "Last 365 days" },
  { value: "lifetime", label: "Lifetime" },
  { value: "custom", label: "Custom (date range)" },
];

// UI period -> key trong tên file TrafficSource.<key>.(js|ts)
export const PERIOD_TO_KEY = {
  last7: "7d",
  last28: "28d",
  last90: "90d",
  last365: "365d",
  lifetime: "lifetime",
};

export function getRangeForPeriod(periodValue, now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const oneDay = 24 * 60 * 60 * 1000;
  const rangeDays = (days) => {
    const end = today;
    const start = new Date(end.getTime() - (days - 1) * oneDay);
    return { start: toYMD(start), end: toYMD(end) };
  };

  if (periodValue === "last7") return rangeDays(7);
  if (periodValue === "last14") return rangeDays(14);
  if (periodValue === "last28") return rangeDays(28);
  if (periodValue === "last90") return rangeDays(90);
  if (periodValue === "last180") return rangeDays(180);
  if (periodValue === "last365") return rangeDays(365);
  if (periodValue === "lifetime") return { start: null, end: null };
  if (periodValue.startsWith("y-")) {
    const y = Number(periodValue.split("-")[1]);
    return { start: `${y}-01-01`, end: `${y}-12-31` };
  }
  if (periodValue === "custom") return { start: null, end: null };
  return { start: null, end: null };
}

// ===== Data loader (hỗ trợ cả Vite & Webpack) =====
// Mặc định dữ liệu ở: /src/data/channels/<channel>/traffic_source/TrafficSource.<key>.{js,ts}
let __entries = [];

/* Vite (khuyên dùng khi dùng Vite) */
try {
  if (typeof import.meta !== "undefined" && import.meta.glob) {
    const mods = import.meta.glob(
      "/src/data/channels/**/traffic_source/TrafficSource.*.{js,ts}",
      { eager: true }
    );
    __entries = Object.entries(mods).map(([abs, mod]) => ({ path: abs, mod }));
  }
} catch { /* ignore */ }

/* Webpack fallback (CRA) */
if (!__entries.length) {
  try {
    // Điều chỉnh đường dẫn nếu module này KHÔNG ở src/lib: dùng "../data" thay vì "../../data"
    const ctx = require.context(
      "../data",
      true,
      /^\.\/channels\/.*\/traffic_source\/TrafficSource\..*\.(js|ts)$/
    );
    __entries = ctx.keys().map((rel) => ({
      // Chuẩn hóa về dạng giống Vite để regex đồng nhất
      path: "/src/data/" + rel.replace(/^\.\//, ""),
      mod: ctx(rel),
    }));
  } catch { /* ignore */ }
}

export function computeChannels() {
  const set = new Set();
  const re = /\/channels\/([^/]+)\/traffic_source\/TrafficSource\./;
  for (const e of __entries) {
    const m = e.path.match(re);
    if (m && m[1]) set.add(m[1]);
  }
  return Array.from(set).sort((a, b) => a.localeCompare(b));
}

export const CHANNEL_OPTIONS = computeChannels().map((root) => ({
  value: root,
  label: root.replace(/\//g, " › "),
}));

export async function loadTrafficSourceByChannelAndKey(channelRoot, key) {
  const re = new RegExp(
    `/channels/${channelRoot}/traffic_source/TrafficSource\\.${key}\\.(js|ts)$`
  );
  const entry = __entries.find((e) => re.test(e.path));
  if (!entry) {
    throw new Error(
      `Không tìm thấy TrafficSource.${key}.* cho channel "${channelRoot}"`
    );
  }
  const mod = entry.mod;
  const arr = Array.isArray(mod?.default)
    ? mod.default
    : Array.isArray(mod?.traffic_source)
      ? mod.traffic_source
      : [];
  return arr;
}

export const pickTicks = (values, maxTicks = 7) => {
  if (!Array.isArray(values) || values.length === 0) return [];
  const toNum = (v) =>
    v instanceof Date ? v.getTime() : Number.isFinite(v) ? v : new Date(String(v)).getTime();

  const uniq = Array.from(
    new Set(values.map(toNum).filter((t) => !Number.isNaN(t)))
  ).sort((a, b) => a - b);

  if (uniq.length <= maxTicks) return uniq.map((t) => new Date(t));

  const step = (uniq.length - 1) / (maxTicks - 1);
  const picks = [];
  for (let i = 0; i < maxTicks; i++) {
    const idx = Math.round(i * step);
    picks.push(uniq[idx]);
  }
  // loại trùng do làm tròn & map về Date
  return Array.from(new Set(picks)).map((t) => new Date(t));
};

let channelAvatarCache = null;
let channelAvatarPromise = null;

export async function getChannelAvatarMap() {
  if (channelAvatarCache) return channelAvatarCache;
  if (channelAvatarPromise) return channelAvatarPromise;

  channelAvatarPromise = api
    .get("/api/content/channels")
    .then((resp) => {
      const items = resp?.data?.items || [];
      const map = {};
      items.forEach((item) => {
        const value = item?.value || item?.id || "";
        if (!value) return;
        map[value] = item?.avatar || null;
      });
      channelAvatarCache = map;
      return map;
    })
    .catch(() => {
      channelAvatarCache = {};
      return channelAvatarCache;
    });

  return channelAvatarPromise;
}

let channelRevenueCache = {};
let channelRevenuePromise = {};

export async function getChannelRevenueMap(range = "lifetime") {
  const cacheKey = String(range || "lifetime");
  if (channelRevenueCache[cacheKey]) return channelRevenueCache[cacheKey];
  if (channelRevenuePromise[cacheKey]) return channelRevenuePromise[cacheKey];

  const params = { range: cacheKey };
  params.include_hidden = true;

  const promise = api
    .get("/api/revenue/channels", { params })
    .then((resp) => {
      const items = resp?.data?.items || [];
      const map = {};
      items.forEach((item) => {
        const value = item?.value || item?.id || "";
        const estimatedRevenue = Number(item?.estimated_revenue ?? item?.estimatedRevenue ?? 0);
        if (!value) return;
        if (Number.isFinite(estimatedRevenue) && estimatedRevenue > 0) {
          map[value] = "$";
        }
      });
      channelRevenueCache[cacheKey] = map;
      return map;
    })
    .catch(() => {
      channelRevenueCache[cacheKey] = {};
      return channelRevenueCache[cacheKey];
    });

  channelRevenuePromise[cacheKey] = promise.finally(() => {
    channelRevenuePromise[cacheKey] = null;
  });
  return channelRevenuePromise[cacheKey];
}


const hashStr = (s) => {
  let h = 53752757 >>> 0;
  const str = String(s);
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
};

/**
 * makeDistinctPaletteV2
 * - Ổn định theo id (hash)
 * - Dùng golden-angle để né trùng hue
 * - Ép khoảng cách hue tối thiểu (minHueGap)
 * - Xoay "lớp" saturation / lightness theo chu kỳ để tăng đa dạng
 * - Hỗ trợ dark mode bằng cách đảo lightness
 */
export const makeDistinctPalette = (
  ids,
  {
    satCycle = [78, 64, 86],           // các mức saturation luân phiên
    lightCycleLight = [52, 62, 42],    // light mode
    lightCycleDark = [60, 70, 50],    // dark mode: nâng lightness để dễ nhìn
    minHueGap = 12,                    // tối thiểu 12° giữa các hue (sau khi làm tròn)
    useDark = false,                   // truyền theo theme.palette.mode === 'dark'
  } = {}
) => {
  const sorted = Array.from(new Set(ids.map(String))).sort();
  const palette = {};
  const usedHues = [];                 // lưu hue đã dùng (số thực), để kiểm tra khoảng cách
  const golden = 137.508;              // độ
  const lightCycle = useDark ? lightCycleDark : lightCycleLight;

  // Hàm kiểm tra khoảng cách hue tối thiểu (đo vòng tròn 0..360)
  const hueTooClose = (h) =>
    usedHues.some((u) => {
      const diff = Math.abs(h - u);
      const d = Math.min(diff, 360 - diff);
      return d < minHueGap;
    });

  sorted.forEach((id, i) => {
    // Hue gốc từ hash (ổn định theo id)
    let hue = hashStr(id) % 360;

    // Nếu quá gần hue đã dùng, nhảy theo golden angle đến khi đủ xa
    let tries = 0;
    while (hueTooClose(hue) && tries < 24) {
      hue = (hue + golden) % 360;
      tries++;
    }
    usedHues.push(hue);

    // Chọn saturation / lightness theo vòng lặp lớp để tăng độ đa dạng
    const s = satCycle[i % satCycle.length];
    // tăng độ “phân lớp” theo bậc thứ i để tránh các nhóm cùng lightness liền nhau
    const layer = ((Math.floor(i / satCycle.length) + (i % 2)) % lightCycle.length);
    const l = lightCycle[layer];

    palette[id] = `hsl(${Math.round(hue)}, ${s}%, ${l}%)`;
  });

  return palette;
};



// ===== helper: parse bucket -> UTC Date để không lệch cột =====
export const toUTCDate = (ymd) => {
  if (!ymd) return null;
  const parts = String(ymd).split("-");
  const y = +parts[0];
  const m = +(parts[1] || 1);
  const d = +(parts[2] || 1);
  return new Date(Date.UTC(y, m - 1, d));
};

export function getMonthRange(offset = 0, base = new Date()) {
  const y = base.getFullYear();
  const m = base.getMonth() - offset;
  const start = new Date(y, m, 1);
  let end;
  if (offset === 0) {
    end = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  } else {
    end = new Date(y, m + 1, 0);
  }
  return { start: toYMD(start), end: toYMD(end) };
}


// ##########################################################################################################################
//TOOL UPLOAD SHORT



// ===== Config & helpers (export) =====
export const VIDEO_EXTS = new Set([".mp4", ".mkv", ".mov", ".webm", ".avi"]);
export const IMAGE_EXTS = new Set([".jpg", ".jpeg", ".png", ".webp", ".gif"]);
export const MAX_DEPTH = 6;
export const MAX_ITEMS = 5000;

export const hasFSAccess =
  typeof window !== "undefined" && "showDirectoryPicker" in window;

export function nowISO() {
  return new Date().toISOString();
}
export function extOf(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}
export function stripExt(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(0, i) : name;
}
export const fmtDate = (iso) => new Date(iso).toLocaleString();

// ===== File system readers (export) =====
async function fileInfoFromHandle(fileHandle) {
  const file = await fileHandle.getFile();
  const e = extOf(file.name);
  const isVideo = VIDEO_EXTS.has(e);
  const isImage = IMAGE_EXTS.has(e);
  return {
    name: file.name,
    size: file.size,
    modified: new Date(file.lastModified || Date.now()).toISOString(),
    type: isVideo ? "video" : isImage ? "image" : "file",
    thumbUrl: isVideo || isImage ? URL.createObjectURL(file) : undefined,
  };
}

export async function readDirectoryRecursive(
  dirHandle,
  rootName,
  { maxDepth = MAX_DEPTH, maxItems = MAX_ITEMS } = {}
) {
  const items = [];
  const rootId = `d:/${rootName}`;
  const toRevoke = [];
  items.push({
    id: rootId,
    name: rootName,
    type: "folder",
    parentId: null,
    modified: nowISO(),
  });

  let count = 1;

  async function walkDirectory(handle, parentId, relPath, depth) {
    if (depth > maxDepth || count >= maxItems) return;

    for await (const [name, entry] of handle.entries()) {
      if (count >= maxItems) break;
      const pathId = `${relPath}/${name}`;
      if (entry.kind === "directory") {
        const dirId = `d:${pathId}`;
        items.push({
          id: dirId,
          name,
          type: "folder",
          parentId,
          modified: nowISO(),
        });
        count++;
        await walkDirectory(entry, dirId, pathId, depth + 1);
      } else if (entry.kind === "file") {
        const info = await fileInfoFromHandle(entry);
        if (info.thumbUrl) toRevoke.push(info.thumbUrl);
        items.push({
          id: `f:${pathId}`,
          name,
          type: info.type,
          parentId,
          size: info.size,
          modified: info.modified,
          thumbUrl: info.thumbUrl,
        });
        count++;
      }
    }
  }

  await walkDirectory(dirHandle, rootId, `/${rootName}`, 1);
  return { items, rootId, toRevoke };
}

// ===== Object URL revoke helper (export) =====
export function useObjectUrlRevoke() {
  const urlsRef = React.useRef([]);
  React.useEffect(
    () => () => {
      urlsRef.current.forEach((u) => URL.revokeObjectURL(u));
    },
    []
  );
  const reset = (newUrls) => {
    urlsRef.current.forEach((u) => URL.revokeObjectURL(u));
    urlsRef.current = [...newUrls];
  };
  return { reset };
}

// ===== Sidebar tree (export) =====
export function SidebarTree({ items, current, onOpen }) {
  const roots = items.filter((it) => it.parentId === null);
  const [open, setOpen] = React.useState({});
  const childrenOf = React.useCallback(
    (id) => items.filter((it) => it.parentId === id),
    [items]
  );
  const toggle = (id) => setOpen((s) => ({ ...s, [id]: !s[id] }));

  const Node = ({ node, depth = 0 }) => {
    const kids = childrenOf(node.id).filter((k) => k.type === "folder");
    const isOpen = !!open[node.id];
    return (
      <Box key={node.id} sx={{ pl: depth * 1.25 }}>
        <Box
          onClick={() => (kids.length ? toggle(node.id) : onOpen(node.id))}
          onDoubleClick={() => onOpen(node.id)}
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            cursor: "pointer",
            px: 1,
            py: 0.75,
            borderRadius: 1,
            bgcolor: current === node.id ? "action.selected" : "transparent",
            "&:hover": { bgcolor: "action.hover" },
            userSelect: "none",
          }}
        >
          <Typography variant="body2" noWrap title={node.name}>
            {node.name}
          </Typography>
          {kids.length ? (
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
              {isOpen ? "−" : "+"}
            </Typography>
          ) : null}
        </Box>
        {isOpen && kids.map((k) => <Node key={k.id} node={k} depth={depth + 1} />)}
      </Box>
    );
  };

  return <Box sx={{ p: 1 }}>{roots.map((r) => <Node key={r.id} node={r} />)}</Box>;
}

// Module.js
export const SHEET_ENDPOINT =
  window.__SHEET_ENDPOINT__ ||
  process.env?.REACT_APP_SHEET_ENDPOINT ||
  "/api/sheet/append";

export const SPREADSHEET_ID =
  window.__SPREADSHEET_ID__ ||
  process.env?.REACT_APP_SPREADSHEET_ID ||
  "";

export async function appendToSheet(row, { worksheetIndex = 5 } = {}) {
  if (!SPREADSHEET_ID) throw new Error("Missing SPREADSHEET_ID");
  const res = await api.post(SHEET_ENDPOINT, {
    sheet_file: SPREADSHEET_ID,
    worksheet_index: worksheetIndex,
    rows: [row],
  });
  return res.data;
}

// Module.js (thêm vào cuối file, và export)
export const SEGMENTER =
  typeof Intl !== "undefined" && Intl.Segmenter
    ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
    : null;

export function countGraphemes(str = "") {
  if (!str) return 0;
  if (!SEGMENTER) return Array.from(str).length; // fallback
  let n = 0;
  const iterator = SEGMENTER.segment(str);
  for (let item = iterator.next(); !item.done; item = iterator.next()) {
    n++;
  }
  return n;

}

export function clampGraphemes(str = "", max = Infinity) {
  if (!str) return "";
  if (!SEGMENTER) return Array.from(str).slice(0, max).join("");
  let out = "", i = 0;
  for (const seg of SEGMENTER.segment(str)) {
    if (i++ >= max) break;
    out += seg.segment;
  }
  return out;
}


export function formatDuration(value) {
  if (value === null || value === undefined || value === "") return "";

  const formatSecondsValue = (totalSeconds) => {
    const safeSeconds = Math.max(0, Math.round(Number(totalSeconds) || 0));
    const h = Math.floor(safeSeconds / 3600);
    const m = Math.floor((safeSeconds % 3600) / 60);
    const s = safeSeconds % 60;

    const parts = [];
    if (h > 0) parts.push(String(h).padStart(2, "0"));
    parts.push(String(m).padStart(2, "0"));
    parts.push(String(s).padStart(2, "0"));
    return parts.join(":");
  };

  if (typeof value === "number") {
    return formatSecondsValue(value);
  }

  if (typeof value !== "string") {
    return String(value);
  }

  const trimmed = value.trim();
  if (!trimmed) return "";
  if (trimmed === "P0D") return "";

  if (/^\d+(\.\d+)?$/.test(trimmed)) {
    return formatSecondsValue(trimmed);
  }

  const match = trimmed.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return trimmed;

  const h = parseInt(match[1] || 0, 10);
  const m = parseInt(match[2] || 0, 10);
  const s = parseInt(match[3] || 0, 10);

  return formatSecondsValue(h * 3600 + m * 60 + s);
}
