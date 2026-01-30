import { useMemo, useState, useEffect } from "react";
import { useTheme } from "@mui/material/styles";
import {
  Box,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TableContainer,
  Paper,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Checkbox,
  Radio,
  Divider,
  ListSubheader,
} from "@mui/material";
import { COUNTRY_FALLBACK } from "../data/countryMapping";
import { ResponsiveChoropleth } from "@nivo/geo";
import { geoFeatures } from "../data/mockGeoFeatures";
import api from "../services/api";

// ===== Helpers =====
const n = (v) => Number(v) || 0;
const formatSeconds = (s) => {
  const sec = Math.max(0, Math.floor(n(s)));
  const m = Math.floor(sec / 60);
  const r = String(sec % 60).padStart(2, "0");
  return `${m}:${r}`;
};
const formatNumber = (v) => n(v).toLocaleString();
const percentStr = (p) => `${n(p).toFixed(2)}%`;

// ===== Metric config =====
const METRICS = {
  views: {
    key: "views",
    label: "Views",
    valueOf: (d) => n(d.views),
    fmt: (v) => formatNumber(v),
  },
  estimatedMinutesWatched: {
    key: "estimatedMinutesWatched",
    label: "Estimated Minutes Watched",
    valueOf: (d) => n(d.estimatedMinutesWatched),
    fmt: (v) => formatNumber(v),
  },
  averageViewDuration: {
    key: "averageViewDuration",
    label: "Avg View Duration",
    valueOf: (d) => n(d.averageViewDuration),
    fmt: (v) => formatSeconds(v),
  },
  averageViewPercentage: {
    key: "averageViewPercentage",
    label: "Avg View %",
    valueOf: (d) => n(d.averageViewPercentage),
    fmt: (v) => `${n(v).toFixed(2)}%`,
  },
  engagedViews: {
    key: "engagedViews",
    label: "Engaged Views",
    valueOf: (d) => n(d.engagedViews),
    fmt: (v) => formatNumber(v),
  },
};

const METRIC_OPTIONS = Object.keys(METRICS).map((k) => ({
  value: k,
  label: METRICS[k].label,
}));

// ===== TABLE COLUMNS =====
const TABLE_COLUMNS = [
  { key: "views", label: "Views", width: 150 },
  { key: "engagedViews", label: "Engaged Views", width: 160 },
  { key: "watchTimeHours", label: "Watch Time (hrs)", width: 160 },
  { key: "averageViewDuration", label: "Avg Duration", width: 150 },
  { key: "averageViewPercentage", label: "Avg %", width: 140 },
];

const GeographyChart = ({ isDashboard = false }) => {
  const theme = useTheme();

  // ===== State =====
  const [rawData, setRawData] = useState([]);
  const [range, setRange] = useState("28d");
  const [channel, setChannel] = useState("");
  const [channels, setChannels] = useState([]);

  // hiện / ẩn cột bảng
  const [visibleColumns, setVisibleColumns] = useState({
    views: true,
    engagedViews: true,
    watchTimeHours: true,
    averageViewDuration: true,
    averageViewPercentage: true,
  });

  // metric dùng cho MAP
  const [metric, setMetric] = useState("views");
  const mconf = METRICS[metric];

  // ===== Fetch data =====
  useEffect(() => {
    const url = `/api/geography?range=${range}${channel ? `&channel=${channel}` : ""
      }`;

    api.get(url)
      .then((r) => r.data)
      .then((json) => {
        setRawData(json.rows || []);

        if (json.availableChannels) {
          const orderKey = (value) =>
            String(value || "")
              .trim()
              .replace(/\s+/g, "_")
              .replace(/[^A-Za-z0-9_.-]/g, "_")
              .toLowerCase();
          const orderList = (() => {
            try {
              return JSON.parse(localStorage.getItem("tokens.order") || "[]");
            } catch {
              return [];
            }
          })()
            .map((name) => String(name || "").replace(/.pickle$/i, ""))
            .map(orderKey)
            .filter(Boolean);
          const orderIndex = new Map(orderList.map((key, idx) => [key, idx]));
          const finalChannels = [...json.availableChannels].sort((a, b) => {
            const ai = orderIndex.has(orderKey(a)) ? orderIndex.get(orderKey(a)) : Number.MAX_SAFE_INTEGER;
            const bi = orderIndex.has(orderKey(b)) ? orderIndex.get(orderKey(b)) : Number.MAX_SAFE_INTEGER;
            if (ai !== bi) return ai - bi;
            return String(a).localeCompare(String(b));
          });
          setChannels(finalChannels);
          if (!channel && finalChannels.length > 0) {
            setChannel(finalChannels[0]);
          }
        }
      })
      .catch((err) => console.error("Geography API error:", err));
  }, [range, channel]);

  // ===== ISO Resolver =====
  const resolvers = useMemo(() => {
    const iso2ToFeatureId = new Map();
    const idToName = new Map();

    for (const f of geoFeatures.features) {
      const id = String(f.id || f.properties?.iso_a3 || "");
      const iso2 = f.properties?.iso_a2?.toUpperCase() || "";
      const name = f.properties?.name || id;

      if (iso2) iso2ToFeatureId.set(iso2, id);
      idToName.set(id, name);
    }

    return {
      resolveId: (code) => {
        const c = String(code).toUpperCase();
        return iso2ToFeatureId.get(c) || COUNTRY_FALLBACK[c] || c;
      },
      nameOf: (id) => idToName.get(id) || id,
    };
  }, []);

  // ===== Normalize data =====
  const data = useMemo(
    () =>
      rawData.map((d) => {
        const id = resolvers.resolveId(d.country);
        return { ...d, id, label: resolvers.nameOf(id) };
      }),
    [rawData, resolvers]
  );

  // ===== MAP DATA =====
  const mapData = useMemo(
    () => data.map((d) => ({ id: d.id, value: mconf.valueOf(d) })),
    [data, mconf]
  );

  const { domainMax } = useMemo(() => {
    const vals = mapData.map((d) => n(d.value));
    return {
      domainMax:
        metric === "averageViewPercentage" ? 100 : Math.max(1, ...vals),
    };
  }, [mapData, metric]);

  // ===== TABLE rows & totals =====
  const { rows, totals } = useMemo(() => {
    const rawRows = data.map((d) => ({
      id: d.id,
      label: d.label,
      views: n(d.views),
      engagedViews: n(d.engagedViews),
      watchTimeHours: n(d.estimatedMinutesWatched) / 60,
      averageViewDuration: n(d.averageViewDuration),
      averageViewPercentage: n(d.averageViewPercentage),
      sortValue: mconf.valueOf(d),
    }));

    const totalViews = rawRows.reduce((s, r) => s + r.views, 0);
    const totalEngaged = rawRows.reduce((s, r) => s + r.engagedViews, 0);
    const totalWatch = rawRows.reduce((s, r) => s + r.watchTimeHours, 0);

    const totals = {
      views: totalViews,
      engagedViews: totalEngaged,
      watchTimeHours: totalWatch,
      averageViewDuration:
        rawRows.reduce((s, r) => s + r.averageViewDuration * r.views, 0) /
        (totalViews || 1),
      averageViewPercentage:
        rawRows.reduce((s, r) => s + r.averageViewPercentage * r.views, 0) /
        (totalViews || 1),
    };

    return {
      totals,
      rows: rawRows
        .map((r) => ({
          ...r,
          viewsPct: totalViews ? (r.views / totalViews) * 100 : 0,
          engagedPct: totalEngaged ? (r.engagedViews / totalEngaged) * 100 : 0,
          watchTimePct: totalWatch ? (r.watchTimeHours / totalWatch) * 100 : 0,
        }))
        .sort((a, b) => b.sortValue - a.sortValue),
    };
  }, [data, mconf]);

  // ===== Value hiển thị trên Select Metrics =====
  const metricsSelectValue = useMemo(() => {
    const colsSelected = Object.entries(visibleColumns)
      .filter(([, v]) => v)
      .map(([k]) => `col:${k}`);
    return [`map:${metric}`, ...colsSelected];
  }, [metric, visibleColumns]);

  const tablePaperSx = useMemo(
    () => ({
      mt: 2,
      px: 2,
      py: 1,
      borderRadius: 3,
      border: "1px solid",
      borderColor:
        theme.palette.mode === "dark"
          ? "rgba(148,163,184,0.22)"
          : "rgba(15,23,42,0.12)",
      background:
        theme.palette.mode === "dark"
          ? "rgba(10,15,24,0.82)"
          : "rgba(255,255,255,0.94)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 14px 28px rgba(15,23,42,0.4)"
          : "0 14px 26px rgba(148,163,184,0.25)",
      overflow: "hidden",
    }),
    [theme.palette.mode]
  );

  const tableHeadSx = useMemo(
    () => ({
      background:
        theme.palette.mode === "dark"
          ? "rgba(15,23,42,0.9)"
          : "rgba(226,232,240,0.85)",
      "& .MuiTableCell-root": {
        fontWeight: 700,
        textTransform: "uppercase",
        letterSpacing: "0.08em",
        fontSize: "0.72rem",
        color:
          theme.palette.mode === "dark"
            ? "rgba(226,232,240,0.85)"
            : "rgba(15,23,42,0.75)",
      },
    }),
    [theme.palette.mode]
  );

  return (
    <Stack spacing={1.5}>

      {/* ===== SELECTORS ===== */}
      <Stack direction="row" spacing={2}>
        {/* Date Range */}
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Date Range</InputLabel>
          <Select
            label="Date Range"
            value={range}
            onChange={(e) => setRange(e.target.value)}
          >
            <MenuItem value="7d">Last 7 days</MenuItem>
            <MenuItem value="28d">Last 28 days</MenuItem>
            <MenuItem value="90d">Last 90 days</MenuItem>
            <MenuItem value="365d">Last 365 days</MenuItem>
            <MenuItem value="lifetime">Lifetime</MenuItem>
          </Select>
        </FormControl>

        {/* ⭐ Metrics = Map metric + Table columns */}
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Metrics</InputLabel>
          <Select
            multiple
            label="Metrics"
            value={metricsSelectValue}
            renderValue={() => "Metrics"}   // 👈 luôn chỉ hiện chữ "Metrics"
          >
            {/* Map metric */}
            <ListSubheader>Map metric</ListSubheader>
            {METRIC_OPTIONS.map((opt) => (
              <MenuItem
                key={`map-${opt.value}`}
                value={`map:${opt.value}`}
                onClick={() => setMetric(opt.value)}
              >
                <Radio checked={metric === opt.value} sx={{
                  mr: 1,
                  color: "#ffffff",
                  "&.Mui-checked": {
                    color: "#ffffff",
                  },
                }} />
                {opt.label}
              </MenuItem>
            ))}

            <Divider sx={{ my: 0.5 }} />

            {/* Table columns */}
            <ListSubheader>Table columns</ListSubheader>
            {TABLE_COLUMNS.map((col) => (
              <MenuItem
                key={`col-${col.key}`}
                value={`col:${col.key}`}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setVisibleColumns((prev) => ({
                    ...prev,
                    [col.key]: !prev[col.key],
                  }));
                }}
              >
                <Checkbox
                  checked={visibleColumns[col.key]}
                  sx={{
                    mr: 1,
                    color: "#ffffff",
                    "&.Mui-checked": {
                      color: "#ffffff",
                    },
                  }}
                />
                {col.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Channel */}
        <FormControl size="small" sx={{ minWidth: 160 }}>
          <InputLabel>Channel</InputLabel>
          <Select
            label="Channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          >
            {channels.map((c) => (
              <MenuItem key={c} value={c}>
                {c}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

      </Stack>

      {/* ===== MAP ===== */}
      <Box sx={{ height: isDashboard ? 360 : 520 }}>
        <ResponsiveChoropleth
          debounceResize={150}
          data={mapData}
          features={geoFeatures.features}
          valueFormat={mconf.fmt}
          domain={[0, domainMax]}
          tooltip={({ feature }) => {
            const iso3 = feature.id;
            const fullname = resolvers.nameOf(iso3);
            const value = feature.value || 0;

            return (
              <Box
                sx={{
                  px: 1.2,
                  py: 0.75,
                  borderRadius: 1,
                  fontSize: 13,
                  fontWeight: 600,
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? "rgba(0,0,0,0.75)"
                      : "rgba(255,255,255,0.95)",
                  boxShadow: 3,
                }}
              >
                <div>{fullname}</div>
                <div>
                  {mconf.label}: {mconf.fmt(value)}
                </div>
              </Box>
            );
          }}

          unknownColor="#999"
          projectionScale={isDashboard ? 80 : 120}
          projectionTranslation={[0.5, 0.67]}
          borderWidth={1.2}
          borderColor="#fff"
        />
      </Box>

      {/* ===== TABLE ===== */}
      <Box sx={{ px: 2 }}>
        <TableContainer component={Paper} elevation={0} sx={tablePaperSx}>
          <Table size="small">
            <TableHead sx={tableHeadSx}>
              <TableRow>
                <TableCell>Country</TableCell>

                {TABLE_COLUMNS.map(col =>
                  visibleColumns[col.key] && (
                    <TableCell
                      key={col.key}
                      align="right"
                      sx={{
                        width: col.width,
                        minWidth: col.width,
                        maxWidth: col.width,
                      }}
                    >
                      {col.label}
                    </TableCell>
                  )
                )}
              </TableRow>
            </TableHead>


            <TableBody>
              {/* ⭐ TOTAL ROW TRÊN CÙNG ⭐ */}
              <TableRow
                sx={{
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? "rgba(30,41,59,0.55)"
                      : "rgba(226,232,240,0.6)",
                }}
              >
                <TableCell sx={{ fontWeight: 700 }}>Total</TableCell>
                {TABLE_COLUMNS.map(
                  (col) =>
                    visibleColumns[col.key] && (
                      <TableCell
                        key={col.key}
                        align="right"
                        sx={{ width: col.width }}
                      >
                        {col.key === "averageViewDuration"
                          ? formatSeconds(totals[col.key])
                          : col.key === "averageViewPercentage"
                            ? percentStr(totals[col.key])
                            : formatNumber(totals[col.key])}
                      </TableCell>
                    )
                )}
              </TableRow>

              {/* DATA ROWS */}
              {rows.map((r) => (
                <TableRow
                  key={r.id}
                  sx={{
                    transition: "transform 0.2s ease, background-color 0.2s ease",
                    "&:hover": {
                      backgroundColor:
                        theme.palette.mode === "dark"
                          ? "rgba(51,65,85,0.55)"
                          : "rgba(226,232,240,0.6)",
                      transform: "translateY(-1px)",
                    },
                  }}
                >
                  <TableCell sx={{ width: 160 }}>{r.label}</TableCell>

                  {TABLE_COLUMNS.map(
                    (col) =>
                      visibleColumns[col.key] && (
                        <TableCell
                          key={col.key}
                          align="right"
                          sx={{ width: col.width }}
                        >
                          {col.key === "views" ? (
                            <>
                              {formatNumber(r.views)}{" "}
                              <span style={{ opacity: 0.6 }}>
                                ({percentStr(r.viewsPct)})
                              </span>
                            </>
                          ) : col.key === "engagedViews" ? (
                            <>
                              {formatNumber(r.engagedViews)}{" "}
                              <span style={{ opacity: 0.6 }}>
                                ({percentStr(r.engagedPct)})
                              </span>
                            </>
                          ) : col.key === "watchTimeHours" ? (
                            <>
                              {formatNumber(r.watchTimeHours)}{" "}
                              <span style={{ opacity: 0.6 }}>
                                ({percentStr(r.watchTimePct)})
                              </span>
                            </>
                          ) : col.key === "averageViewDuration" ? (
                            formatSeconds(r.averageViewDuration)
                          ) : col.key === "averageViewPercentage" ? (
                            percentStr(r.averageViewPercentage)
                          ) : (
                            formatNumber(r[col.key])
                          )}
                        </TableCell>
                      )
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Stack>
  );
};

export default GeographyChart;
