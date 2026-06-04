// components/research/primitives.jsx — UI primitives tái dùng cho 22 tab báo cáo
import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  useTheme,
} from "@mui/material";

const fmtNum = (v) => {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return v.toLocaleString("en-US");
  return String(v);
};

export const num = fmtNum;

export const EmptyState = ({ text = "Chưa có dữ liệu cho mục này." }) => {
  const theme = useTheme();
  return (
    <Box
      sx={{
        p: 4,
        textAlign: "center",
        color: theme.palette.text.secondary,
        border: `1px dashed ${theme.palette.divider}`,
        borderRadius: 2,
      }}
    >
      <Typography variant="body2">{text}</Typography>
    </Box>
  );
};

export const SectionCard = ({ title, subtitle, action, children, sx }) => {
  const theme = useTheme();
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        mb: 2,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 2,
        bgcolor: theme.palette.background.paper,
        ...sx,
      }}
    >
      {(title || action) && (
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={subtitle ? 0.25 : 1}>
          {title && (
            <Typography variant="subtitle1" fontWeight={700}>
              {title}
            </Typography>
          )}
          {action}
        </Box>
      )}
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1.25 }}>
          {subtitle}
        </Typography>
      )}
      {children}
    </Paper>
  );
};

export const StatGrid = ({ stats = [] }) => {
  const theme = useTheme();
  const items = stats.filter(Boolean);
  if (!items.length) return null;
  return (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
        gap: 1.25,
      }}
    >
      {items.map((s, i) => (
        <Box
          key={i}
          sx={{
            p: 1.25,
            borderRadius: 2,
            border: `1px solid ${theme.palette.divider}`,
            bgcolor:
              theme.palette.mode === "dark"
                ? "rgba(255,255,255,0.03)"
                : "rgba(15,23,42,0.02)",
          }}
        >
          <Typography variant="caption" color="text.secondary" noWrap title={s.label}>
            {s.label}
          </Typography>
          <Typography variant="h6" fontWeight={700} sx={{ lineHeight: 1.3 }}>
            {fmtNum(s.value)}
          </Typography>
          {s.hint && (
            <Typography variant="caption" color="text.secondary">
              {s.hint}
            </Typography>
          )}
        </Box>
      ))}
    </Box>
  );
};

// columns: [{key, label, align?, render?(row)}]
export const DataTable = ({ columns = [], rows = [], size = "small", limit = 10 }) => {
  const theme = useTheme();
  if (!rows?.length) return <EmptyState />;
  const shown = limit ? rows.slice(0, limit) : rows;
  return (
    <TableContainer
      component={Paper}
      elevation={0}
      sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}
    >
      <Table
        stickyHeader
        size={size}
        sx={{
          "& tbody tr:nth-of-type(odd)": {
            bgcolor: theme.palette.mode === "dark" ? "rgba(255,255,255,0.03)" : "rgba(15,23,42,0.025)",
          },
        }}
      >
        <TableHead>
          <TableRow>
            {columns.map((c) => (
              <TableCell
                key={c.key}
                align={c.align || "left"}
                sx={{ fontWeight: 700, whiteSpace: "nowrap", bgcolor: theme.palette.background.paper }}
              >
                {c.label}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {shown.map((row, ri) => (
            <TableRow key={ri} hover>
              {columns.map((c) => (
                <TableCell key={c.key} align={c.align || "left"}>
                  {c.render ? c.render(row) : fmtNum(row[c.key])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export const TextBlock = ({ text }) => {
  if (!text || !String(text).trim()) return <EmptyState />;
  return (
    <Typography
      component="pre"
      variant="body2"
      sx={{
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
        fontFamily: "inherit",
        m: 0,
        lineHeight: 1.6,
      }}
    >
      {text}
    </Typography>
  );
};

const SEV_COLOR = {
  high: "error",
  med: "warning",
  medium: "warning",
  low: "info",
  info: "default",
};

export const SevChip = ({ sev }) => (
  <Chip size="small" label={sev || "info"} color={SEV_COLOR[sev] || "default"} variant="outlined" />
);

const PRIO_COLOR = {
  high: "error",
  med: "warning",
  medium: "warning",
  low: "default",
  good: "success",
};

export const PrioChip = ({ value }) => {
  if (value === null || value === undefined || value === "") return "—";
  const key = String(value).toLowerCase();
  return <Chip size="small" label={String(value).toUpperCase()} color={PRIO_COLOR[key] || "default"} />;
};

export const Pill = ({ label, color = "default" }) => (
  <Chip size="small" label={label} color={color} sx={{ mr: 0.5, mb: 0.5 }} />
);
