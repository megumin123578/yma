import {
  Box,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Switch,
  Tooltip,
  Typography,
} from "@mui/material";
import { useCallback, useMemo, useState } from "react";
import Header from "../../components/Header";
import SmmstoreAnalytics from "../../components/SmmstoreAnalytics";
import * as XLSX from "xlsx";
import DownloadOutlinedIcon from "@mui/icons-material/DownloadOutlined";

const SmmstoreAnalyticsScene = () => {
  const [viewMode, setViewMode] = useState("orders");
  const [analyticsData, setAnalyticsData] = useState(null);
  const [downloadAnchor, setDownloadAnchor] = useState(null);
  const downloadOpen = Boolean(downloadAnchor);

  const currentRows = useMemo(() => {
    if (!analyticsData) return [];
    if (viewMode === "totals") {
      return (analyticsData?.totals?.by_channel || []).map((item) => ({
        Channel: item.link,
        Charge: item.charge,
      }));
    }
    return analyticsData?.orders || [];
  }, [analyticsData, viewMode]);

  const currentColumns = useMemo(() => {
    if (viewMode === "totals") {
      return ["Channel", "Charge"];
    }
    return [
      "ID",
      "Date",
      "Link",
      "Charge",
      "Start count",
      "Quantity",
      "Service",
      "Status",
      "Remains",
    ];
  }, [viewMode]);

  const downloadFile = useCallback((content, filename, mime) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, []);

  const formatMonthLabel = useCallback((value) => {
    if (!value) return "unknown-month";
    const match = String(value).match(/^(\d{4})-(\d{2})$/);
    if (!match) return String(value).replace(/\s+/g, "-");
    return `${match[2]}-${match[1]}`;
  }, []);

  const toCsv = useCallback(() => {
    if (!currentRows.length) return;
    const header = currentColumns.join(",");
    const rows = currentRows.map((row) =>
      currentColumns
        .map((col) => {
          const value = row?.[col] ?? "";
          const escaped = String(value).replace(/"/g, '""');
          return `"${escaped}"`;
        })
        .join(",")
    );
    const csv = [header, ...rows].join("\n");
    const monthLabel = formatMonthLabel(analyticsData?.month);
    const typeLabel = viewMode === "totals" ? "totals" : "orders";
    downloadFile(
      csv,
      `smmstore_${typeLabel}_${monthLabel}.csv`,
      "text/csv;charset=utf-8;"
    );
  }, [analyticsData?.month, currentColumns, currentRows, downloadFile, formatMonthLabel, viewMode]);

  const toExcel = useCallback(() => {
    if (!currentRows.length) return;
    const aoa = [
      currentColumns,
      ...currentRows.map((row) =>
        currentColumns.map((col) => row?.[col] ?? "")
      ),
    ];
    const sheet = XLSX.utils.aoa_to_sheet(aoa);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, sheet, "Analytics");
    const monthLabel = formatMonthLabel(analyticsData?.month);
    const typeLabel = viewMode === "totals" ? "totals" : "orders";
    XLSX.writeFile(workbook, `smmstore_${typeLabel}_${monthLabel}.xlsx`, {
      bookType: "xlsx",
    });
  }, [analyticsData?.month, currentColumns, currentRows, formatMonthLabel, viewMode]);

  return (
    <Box mx="20px" mt="0" mb="20px">
      <Stack
        direction="row"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={2}
      >
        <Header
          title="SMMStore Analytics"
          subtitle="Manage how much money spent last month"
        />
        <Stack direction="row" alignItems="center" spacing={1.2}>
          <Tooltip title="Download">
            <span>
              <IconButton
                size="small"
                onClick={(e) => setDownloadAnchor(e.currentTarget)}
                disabled={!currentRows.length}
                sx={{
                  borderRadius: 2,
                  border: "1px solid rgba(148,163,184,0.5)",
                  color: "rgba(226,232,240,0.9)",
                  "&:hover": {
                    borderColor: "rgba(56,189,248,0.7)",
                    backgroundColor: "rgba(56,189,248,0.12)",
                  },
                }}
              >
                <DownloadOutlinedIcon fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
          <Menu
            anchorEl={downloadAnchor}
            open={downloadOpen}
            onClose={() => setDownloadAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
            transformOrigin={{ vertical: "top", horizontal: "right" }}
          >
            <MenuItem
              onClick={() => {
                setDownloadAnchor(null);
                toCsv();
              }}
            >
              Download CSV
            </MenuItem>
            <MenuItem
              onClick={() => {
                setDownloadAnchor(null);
                toExcel();
              }}
            >
              Download Excel
            </MenuItem>
          </Menu>
          <Typography variant="body2" fontWeight={600}>
            Orders
          </Typography>
          <Switch
            checked={viewMode === "totals"}
            onChange={(e) =>
              setViewMode(e.target.checked ? "totals" : "orders")
            }
            color="warning"
            sx={{
              "& .MuiSwitch-track": {
                backgroundColor: "rgba(148,163,184,0.35)",
                opacity: 1,
              },
              "& .MuiSwitch-thumb": {
                boxShadow: "0 6px 14px rgba(15,23,42,0.35)",
              },
              "&.Mui-checked .MuiSwitch-track": {
                backgroundColor: "rgba(34,197,94,0.45)",
                opacity: 1,
              },
              "&.Mui-checked .MuiSwitch-thumb": {
                boxShadow: "0 6px 16px rgba(34,197,94,0.45)",
              },
            }}
          />
          <Typography variant="body2" fontWeight={600}>
            Totals
          </Typography>
        </Stack>
      </Stack>
      <SmmstoreAnalytics viewMode={viewMode} onDataChange={setAnalyticsData} />
    </Box>
  );
};

export default SmmstoreAnalyticsScene;
