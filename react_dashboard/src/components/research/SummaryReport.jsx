import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Chip,
  CircularProgress,
  FormControl,
  MenuItem,
  Select,
  Typography,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { DataTable, EmptyState, SectionCard, TextBlock, num } from "./primitives";
import { getResearchSummary } from "../../services/researchService";
import {
  getSharedFilterControlSx,
  getSharedSelectMenuProps,
} from "../filterStyles";

const sg = (v) => {
  const n = Number(v) || 0;
  return (n > 0 ? "+" : "") + num(n);
};

// "2026-06-05 14:56" -> ngày "2026-06-05", giờ "14:56"
const snapYmd = (dt) => String(dt || "").split(" ")[0];
const snapHm = (dt) => String(dt || "").split(" ")[1] || "";
// "2026-06-05" -> "05/06/2026" (đồng bộ format các page báo cáo khác)
const fmtSnapDay = (ymd) => {
  const [y, m, d] = String(ymd || "").split("-");
  return y && m && d ? `${d}/${m}/${y}` : String(ymd || "");
};

const SummaryReport = () => {
  const theme = useTheme();
  const filterControlSx = getSharedFilterControlSx(theme, { flex: "0 0 auto" });
  const selectMenuProps = getSharedSelectMenuProps(theme);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = (opts = {}) => {
    setLoading(true);
    setError("");
    getResearchSummary(opts)
      .then(setData)
      .catch((e) => {
        setData(null);
        setError(e?.response?.data?.detail || e.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const snapshots = data?.snapshots || [];
  const snapshotId = data?.snapshot_id || "";

  // Tách ngày / giờ: dropdown ngày, kèm dropdown giờ khi 1 ngày có ≥2 báo cáo.
  const selSnap = snapshots.find((s) => s.id === snapshotId);
  const snapDays = [...new Set(snapshots.map((s) => snapYmd(s.date)))];
  const snapDay = snapYmd(selSnap?.date) || snapDays[0] || "";
  const snapDayItems = snapshots.filter((s) => snapYmd(s.date) === snapDay);

  const warnings = useMemo(
    () =>
      (data?.watchlists || []).flatMap((w) =>
        (w.warnings || []).map((warning) => ({
          watchlist: w.name,
          channel: w.self_title,
          warning,
        }))
      ),
    [data]
  );

  if (loading && !data) {
    return (
      <Box display="flex" alignItems="center" gap={1}>
        <CircularProgress size={18} />
        <Typography variant="body2" color="text.secondary">
          Đang tạo báo cáo tổng hợp…
        </Typography>
      </Box>
    );
  }

  if (error && !data) return <EmptyState text={`Lỗi: ${error}`} />;
  if (!data) return <EmptyState text="Chưa có dữ liệu báo cáo tổng hợp." />;

  const wlRows = data.watchlists || [];
  const topVideos = data.cross_top_videos || [];
  const opps = data.cross_wl_opps || [];
  const oppColumns = opps.length
    ? Object.keys(opps[0])
        .filter((k) => ["string", "number", "boolean"].includes(typeof opps[0][k]))
        .slice(0, 8)
        .map((k) => ({ key: k, label: k.replace(/_/g, " ") }))
    : [];

  const pos = theme.palette.success.main;
  const neg = theme.palette.error.main;
  const deltaColor = (v) =>
    Number(v) > 0 ? pos : Number(v) < 0 ? neg : theme.palette.text.secondary;
  const Delta = (v) => (
    <Typography component="span" variant="body2" fontWeight={700} sx={{ color: deltaColor(v) }}>
      {sg(v)}
    </Typography>
  );

  const kpis = [
    {
      label: "Watchlists",
      value: num(data.n_wl),
      hint: "Đang theo dõi",
      accent: theme.palette.primary.main,
    },
    {
      label: "Người đăng ký",
      value: num(data.total_subs),
      hint: "Tổng hiện tại",
      accent: theme.palette.primary.main,
    },
    {
      label: "Δ Subs · 7 ngày",
      value: sg(data.total_subs_delta_7d),
      hint: "So với tuần trước",
      accent: deltaColor(data.total_subs_delta_7d),
      color: deltaColor(data.total_subs_delta_7d),
    },
    {
      label: "Δ Views · 7 ngày",
      value: sg(data.total_views_delta_7d),
      hint: "Tăng trưởng gần nhất",
      accent: deltaColor(data.total_views_delta_7d),
      color: deltaColor(data.total_views_delta_7d),
    },
    {
      label: "Cảnh báo",
      value: num(data.n_warnings),
      hint: data.n_warnings ? "Cần xử lý" : "Tốt, không có",
      accent: data.n_warnings ? theme.palette.warning.main : pos,
      color: data.n_warnings ? theme.palette.warning.main : pos,
    },
  ];

  const cardBg =
    theme.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(15,23,42,0.02)";
  const subtleBorder = `1px solid ${theme.palette.divider}`;

  const dateBar = (
    <Box display="flex" alignItems="center" gap={1.5} mb={2} flexWrap="wrap">
      {snapshots.length > 0 && (
        <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 175 } }}>
          <Select
            value={snapDay}
            onChange={(e) => {
              const newest = snapshots.find((s) => snapYmd(s.date) === e.target.value);
              if (newest) load({ snapshot: newest.id });
            }}
            disabled={loading}
            MenuProps={selectMenuProps}
            renderValue={(val) => `🗓 ${fmtSnapDay(val)}`}
          >
            {snapDays.map((d) => (
              <MenuItem key={d} value={d}>
                {fmtSnapDay(d)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {snapDayItems.length > 1 && (
        <FormControl size="small" sx={{ ...filterControlSx, minWidth: { xs: "100%", sm: 130 } }}>
          <Select
            value={snapshotId}
            onChange={(e) => load({ snapshot: e.target.value })}
            disabled={loading}
            MenuProps={selectMenuProps}
            renderValue={(val) => `🕐 ${snapHm(snapshots.find((s) => s.id === val)?.date)}`}
          >
            {snapDayItems.map((it) => (
              <MenuItem key={it.id} value={it.id}>
                {snapHm(it.date)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {loading && <CircularProgress size={18} />}
      {error && <Chip size="small" color="error" variant="outlined" label={error} />}
    </Box>
  );

  return (
    <Box>
      {dateBar}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(165px, 1fr))",
          gap: 1.5,
          mb: 2,
        }}
      >
        {kpis.map((k) => (
          <Box
            key={k.label}
            sx={{
              p: 1.5,
              borderRadius: 2,
              border: subtleBorder,
              borderLeft: `3px solid ${k.accent}`,
              bgcolor: alpha(k.accent, theme.palette.mode === "dark" ? 0.1 : 0.05),
            }}
          >
            <Typography variant="caption" color="text.secondary" noWrap title={k.label}>
              {k.label}
            </Typography>
            <Typography variant="h5" fontWeight={800} sx={{ lineHeight: 1.3, color: k.color }}>
              {k.value}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {k.hint}
            </Typography>
          </Box>
        ))}
      </Box>

      <SectionCard
        title="Tình hình từng kênh"
        subtitle="Sắp xếp theo Δ views 7 ngày · kênh nóng nhất lên đầu"
        action={<Chip size="small" variant="outlined" label={`${wlRows.length} kênh`} />}
      >
        <DataTable
          rows={wlRows}
          limit={null}
          columns={[
            {
              key: "self_title",
              label: "Kênh chính",
              render: (r) => (
                <Box>
                  <Typography variant="body2" fontWeight={700} noWrap>
                    {r.self_title || r.name || "—"}
                  </Typography>
                  {r.name && r.name !== r.self_title && (
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {r.name}
                    </Typography>
                  )}
                </Box>
              ),
            },
            { key: "subs", label: "Subs", align: "right", render: (r) => (
              <Typography variant="body2" fontWeight={600}>{num(r.subs)}</Typography>
            ) },
            { key: "subs_delta_7d", label: "Δ Subs 7d", align: "right", render: (r) => Delta(r.subs_delta_7d) },
            { key: "views_delta_7d", label: "Δ Views 7d", align: "right", render: (r) => Delta(r.views_delta_7d) },
            { key: "avg_daily_views_7d", label: "View/ngày TB", align: "right", render: (r) => num(r.avg_daily_views_7d) },
            {
              key: "top_videos_today",
              label: "Video hot nhất",
              render: (r) => {
                const v = (r.top_videos_today || [])[0];
                if (!v) return <Typography variant="body2" color="text.secondary">—</Typography>;
                return (
                  <Box>
                    <Typography variant="body2" noWrap sx={{ maxWidth: 260 }} title={v.title}>
                      {v.title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      ~{num(v.vpd)} view/ngày
                    </Typography>
                  </Box>
                );
              },
            },
          ]}
        />
      </SectionCard>

      <SectionCard
        title="Top video nổi bật toàn công ty"
        subtitle="Video bùng nổ xuyên ngách"
        action={topVideos.length ? <Chip size="small" variant="outlined" label={`${topVideos.length} video`} /> : null}
      >
        {topVideos.length ? (
          <DataTable
            rows={topVideos}
            limit={null}
            columns={[
              {
                key: "title",
                label: "Video",
                render: (r) => (
                  <Typography variant="body2" fontWeight={600} sx={{ maxWidth: 340 }} noWrap title={r.title}>
                    {r.title}
                  </Typography>
                ),
              },
              { key: "channel", label: "Kênh" },
              { key: "wl_name", label: "Watchlist" },
              { key: "views", label: "Views", align: "right", render: (r) => num(r.views) },
              { key: "vpd", label: "View/ngày", align: "right", render: (r) => (r.vpd ? num(r.vpd) : "—") },
              {
                key: "mult",
                label: "Outlier",
                align: "right",
                render: (r) =>
                  r.mult ? (
                    <Chip size="small" color="error" variant="outlined" label={`${r.mult}×`} />
                  ) : (
                    "—"
                  ),
              },
            ]}
          />
        ) : (
          <EmptyState text="Chưa có video nổi bật." />
        )}
      </SectionCard>

      <SectionCard
        title="Cảnh báo"
        subtitle="Kênh tụt subs, video bị ẩn/xoá cần kiểm tra"
        action={
          <Chip
            size="small"
            color={warnings.length ? "warning" : "success"}
            variant="outlined"
            label={warnings.length ? `${warnings.length} cảnh báo` : "Không có"}
          />
        }
      >
        {warnings.length ? (
          <DataTable
            rows={warnings}
            limit={null}
            columns={[
              {
                key: "channel",
                label: "Kênh",
                render: (r) => (
                  <Box>
                    <Typography variant="body2" fontWeight={700}>{r.channel || "—"}</Typography>
                    <Typography variant="caption" color="text.secondary">{r.watchlist}</Typography>
                  </Box>
                ),
              },
              {
                key: "warning",
                label: "Nội dung",
                render: (r) => (
                  <Typography variant="body2" sx={{ color: theme.palette.warning.main }}>
                    {r.warning}
                  </Typography>
                ),
              },
            ]}
          />
        ) : (
          <EmptyState text="Không có cảnh báo." />
        )}
      </SectionCard>

      <SectionCard
        title="Cơ hội Cross-WL"
        subtitle="Cụm đang viral ở WL này → gợi ý thử cho WL khác có cùng tệp người xem"
      >
        {opps.length ? (
          <DataTable rows={opps} columns={oppColumns} limit={20} />
        ) : (
          <EmptyState text="Chưa có cơ hội Cross-WL." />
        )}
      </SectionCard>

      <SectionCard title="Tóm lược chiến lược từng kênh">
        {wlRows.some((w) => w.strategy_preview) ? (
          <Box
            sx={{
              display: "grid",
              gap: 1.5,
              gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
            }}
          >
            {wlRows
              .filter((w) => w.strategy_preview)
              .map((w) => (
                <Box
                  key={w.wid}
                  sx={{
                    p: 1.75,
                    borderRadius: 2,
                    border: subtleBorder,
                    borderLeft: `3px solid ${theme.palette.secondary.main}`,
                    bgcolor: cardBg,
                  }}
                >
                  <Typography variant="subtitle2" fontWeight={700} gutterBottom>
                    {w.name}
                  </Typography>
                  <TextBlock text={w.strategy_preview} />
                </Box>
              ))}
          </Box>
        ) : (
          <EmptyState text="Chưa có tóm lược chiến lược." />
        )}
      </SectionCard>
    </Box>
  );
};

export default SummaryReport;
