import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  Tabs,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import StorageRoundedIcon from "@mui/icons-material/StorageRounded";
import DnsRoundedIcon from "@mui/icons-material/DnsRounded";
import EastRoundedIcon from "@mui/icons-material/EastRounded";

import api from "../services/api";


const GMAIL_APP_PASSWORD_URL =
  "https://myaccount.google.com/apppasswords?continue=https://myaccount.google.com/security?gar%3DWzI4MV0%26hl%3Den%26authuser%3D0%26rapt%3DAEjHL4N2ZCtAmejTdU1B_yLRBSQnTW3O6JdoCcy_hZd5VFQzhI2gY0vZI-IjGq30JdDYz57LMBB5uwe6ZCrFNgpcD7rGfEHV3CNkKI8o94iA6RkjdDQqOTc%26utm_source%3DOGB%26utm_medium%3Dact&pli=1&rapt=AEjHL4Oinn7oeWvsu4jswaDQ7qheJeXNrGod1MqSnOUr7oddM7BsZhOvfUP0GgK7cWjdMMO-Pdf7HXGruTKrMoeQRRX6Dqv2boAljUWm9XPLJBm_cy9Ly8k";
const MIN_IMAP_PASSWORD_LENGTH = 16;


const normalizeImapPassword = (value) => String(value || "").replace(/\s+/g, "");


const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
};


const formatNumber = (value) => {
  return Number(value || 0).toLocaleString();
};


const decodeHtmlEntities = (value) => {
  if (!value || typeof window === "undefined") return value || "";
  const textarea = document.createElement("textarea");
  textarea.innerHTML = value;
  return textarea.value;
};


const toPlainPreviewText = (value) => {
  const raw = String(value || "");
  if (!raw) return "-";

  const decoded = decodeHtmlEntities(raw);
  const withoutTags = decoded.replace(/<[^>]*>/g, " ");
  const withoutBracketArtifacts = withoutTags.replace(/\[(?:image|cid:[^\]]+|attachment|logo)[^\]]*\]/gi, " ");
  const compact = withoutBracketArtifacts.replace(/\s+/g, " ").trim();

  return compact || "-";
};


const truncatePreviewText = (value, maxLength = 90) => {
  const text = toPlainPreviewText(value);
  if (text === "-" || text.length <= maxLength) return text;
  return `${text.slice(0, maxLength).trimEnd()}...`;
};


const statusChipColor = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "error") return "error";
  if (normalized === "ok") return "success";
  if (normalized === "matched") return "info";
  return "default";
};


const StatCard = ({ icon, label, value, accent }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  return (
    <Paper
      sx={{
        p: 1.6,
        borderRadius: 3,
        position: "relative",
        overflow: "hidden",
        border: "1px solid",
        borderColor: isDark ? alpha("#94a3b8", 0.18) : alpha("#0f172a", 0.1),
        background: isDark
          ? `linear-gradient(140deg, rgba(15,23,42,0.96) 0%, rgba(30,41,59,0.92) 55%, ${alpha(accent, 0.2)} 100%)`
          : `linear-gradient(140deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.98) 58%, ${alpha(accent, 0.14)} 100%)`,
        boxShadow: isDark
          ? "0 16px 28px rgba(2,6,23,0.34)"
          : "0 14px 24px rgba(148,163,184,0.18)",
        minHeight: 102,
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Typography
            variant="body2"
            sx={{
              color: "text.secondary",
              opacity: isDark ? 0.82 : 0.9,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            {label}
          </Typography>
          <Typography variant="h4" fontWeight={800} mt={0.75} color="text.primary">
            {value}
          </Typography>
        </Box>
        <Box
          sx={{
            width: 38,
            height: 38,
            borderRadius: 2,
            display: "grid",
            placeItems: "center",
            bgcolor: alpha(accent, isDark ? 0.14 : 0.12),
            color: accent,
            border: "1px solid",
            borderColor: alpha(accent, isDark ? 0.22 : 0.16),
          }}
        >
          {icon}
        </Box>
      </Stack>
    </Paper>
  );
};


const MailMonitor = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const MAILS_PER_PAGE = 50;
  const [overview, setOverview] = useState({ summary: {}, items: [] });
  const [messages, setMessages] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({
    vpsId: "",
    accountEmail: "",
    mailbox: "",
    status: "matched",
    search: "",
  });
  const [error, setError] = useState("");
  const [autoRefresh] = useState(true);
  const [agentForm, setAgentForm] = useState({
    vpsName: "",
    accounts: [{ email: "", password: "" }],
  });
  const [agentDownload, setAgentDownload] = useState({
    loading: false,
    error: "",
    success: "",
  });
  const [activeTab, setActiveTab] = useState("messages");
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [selectedMessageDetail, setSelectedMessageDetail] = useState(null);
  const [selectedMessageLoading, setSelectedMessageLoading] = useState(false);
  const [selectedMessageError, setSelectedMessageError] = useState("");
  const [machineDeleteTarget, setMachineDeleteTarget] = useState(null);
  const [machineDeleteLoading, setMachineDeleteLoading] = useState(false);
  const [machineDeleteError, setMachineDeleteError] = useState("");
  const [machineDeleteSuccess, setMachineDeleteSuccess] = useState("");
  const [mailPage, setMailPage] = useState(0);

  const overviewItems = useMemo(
    () =>
      (Array.isArray(overview?.items) ? overview.items : []).filter(
        (item) => item && typeof item === "object"
      ),
    [overview]
  );

  const vpsOptions = useMemo(
    () => [...new Set(overviewItems.map((item) => item.vps_id).filter(Boolean))],
    [overviewItems]
  );

  const mailboxOptions = useMemo(() => {
    return [
      ...new Set(
        overviewItems
          .filter((item) => !filters.vpsId || item.vps_id === filters.vpsId)
          .filter((item) => !filters.accountEmail || item.account_email === filters.accountEmail)
          .map((item) => item.mailbox)
          .filter(Boolean)
      ),
    ];
  }, [filters.accountEmail, filters.vpsId, overviewItems]);

  const accountOptions = useMemo(() => {
    return [
      ...new Set(
        overviewItems
          .filter((item) => !filters.vpsId || item.vps_id === filters.vpsId)
          .map((item) => item.account_email)
          .filter(Boolean)
      ),
    ];
  }, [filters.vpsId, overviewItems]);

  const messageItems = useMemo(
    () =>
      (Array.isArray(messages?.items) ? messages.items : []).filter(
        (item) => item && typeof item === "object"
      ),
    [messages]
  );

  const loadData = useCallback(async () => {
    setError("");
    try {
      const [overviewResp, messagesResp] = await Promise.all([
        api.get("/api/mail/overview"),
        api.get("/api/mail/messages", {
          params: {
            vps_id: filters.vpsId || undefined,
            account_email: filters.accountEmail || undefined,
            mailbox: filters.mailbox || undefined,
            status: filters.status || undefined,
            search: filters.search || undefined,
            limit: MAILS_PER_PAGE,
            offset: mailPage * MAILS_PER_PAGE,
            per_account_limit: MAILS_PER_PAGE,
          },
        }),
      ]);
      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load email manager data.");
    }
  }, [MAILS_PER_PAGE, filters.accountEmail, filters.mailbox, filters.search, filters.status, filters.vpsId, mailPage]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    setMailPage(0);
  }, [filters.vpsId, filters.accountEmail, filters.mailbox, filters.status, filters.search]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => {
      loadData();
    }, 45000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadData]);

  const handleAgentAccountChange = useCallback((index, field, value) => {
    setAgentForm((current) => ({
      ...current,
      accounts: current.accounts.map((account, accountIndex) =>
        accountIndex === index
          ? {
              ...account,
              [field]: value,
            }
          : account
      ),
    }));
  }, []);

  const handleAddAgentAccount = useCallback(() => {
    setAgentForm((current) => ({
      ...current,
      accounts: [...current.accounts, { email: "", password: "" }],
    }));
  }, []);

  const handleRemoveAgentAccount = useCallback((index) => {
    setAgentForm((current) => {
      if (current.accounts.length <= 1) {
        return current;
      }
      return {
        ...current,
        accounts: current.accounts.filter((_, accountIndex) => accountIndex !== index),
      };
    });
  }, []);

  const handleAgentDownload = useCallback(async () => {
    const vpsName = agentForm.vpsName.trim();
    const normalizedAccounts = agentForm.accounts
      .map((account) => ({
        email: String(account?.email || "").trim(),
        password: normalizeImapPassword(account?.password),
      }))
      .filter((account) => account.email || account.password);

    if (!vpsName) {
      setAgentDownload({
        loading: false,
        error: "Name is required.",
        success: "",
      });
      return;
    }

    if (normalizedAccounts.length === 0) {
      setAgentDownload({
        loading: false,
        error: "At least one email account is required.",
        success: "",
      });
      return;
    }

    const invalidIndex = normalizedAccounts.findIndex(
      (account) => !account.email || !account.password
    );
    if (invalidIndex >= 0) {
      setAgentDownload({
        loading: false,
        error: `Email and IMAP password are required for account ${invalidIndex + 1}.`,
        success: "",
      });
      return;
    }

    const shortPasswordIndex = normalizedAccounts.findIndex(
      (account) => account.password.length < MIN_IMAP_PASSWORD_LENGTH
    );
    if (shortPasswordIndex >= 0) {
      setAgentDownload({
        loading: false,
        error: `IMAP password for account ${shortPasswordIndex + 1} must be at least ${MIN_IMAP_PASSWORD_LENGTH} characters.`,
        success: "",
      });
      return;
    }

    setAgentDownload({
      loading: true,
      error: "",
      success: "",
    });

    try {
      const response = await api.post(
        "/api/mail/agent-template",
        {
          vps_id: vpsName,
          accounts: normalizedAccounts,
        },
        {
          responseType: "blob",
        }
      );

      const contentDisposition = response.headers?.["content-disposition"] || "";
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      const filename = filenameMatch?.[1] || "mail_agent_bundle.zip";
      const vpsId = response.headers?.["x-agent-vps-id"] || vpsName;

      const blob = new Blob([response.data], {
        type: response.headers?.["content-type"] || "application/zip",
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setAgentForm((current) => ({
        ...current,
        accounts: current.accounts.map((account) => ({
          ...account,
          password: "",
        })),
      }));
      setAgentDownload({
        loading: false,
        error: "",
        success: `Downloaded script for ${vpsId}.`,
      });
    } catch (err) {
      setAgentDownload({
        loading: false,
        error: err?.response?.data?.detail || err?.message || "Failed to generate script.",
        success: "",
      });
    }
  }, [agentForm.accounts, agentForm.vpsName]);

  const summary = overview?.summary || {};
  const filterPanelBg =
    theme.palette.mode === "dark"
      ? "rgba(15,23,42,0.82)"
      : "rgba(255,255,255,0.94)";
  const tablePaperSx = useMemo(
    () => ({
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
      "& .MuiTableBody-root .MuiTableRow-root:nth-of-type(even)": {
        backgroundColor:
          theme.palette.mode === "dark"
            ? "rgba(148,163,184,0.05)"
            : "rgba(148,163,184,0.08)",
      },
      "& .MuiTableBody-root .MuiTableRow-root:hover": {
        backgroundColor:
          theme.palette.mode === "dark"
            ? "rgba(96,165,250,0.10)"
            : "rgba(59,130,246,0.08)",
      },
      "& .MuiTableCell-root": {
        borderColor:
          theme.palette.mode === "dark"
            ? "rgba(148,163,184,0.12)"
            : "rgba(148,163,184,0.18)",
      },
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
  const selectedMessagePayload =
    selectedMessageDetail?.payload && typeof selectedMessageDetail.payload === "object"
      ? selectedMessageDetail.payload
      : {};
  const selectedMessageBody =
    selectedMessagePayload.text_body ||
    selectedMessagePayload.textBody ||
    selectedMessageDetail?.snippet ||
    "";
  const selectedMessageHtml =
    selectedMessagePayload.html_body || selectedMessagePayload.htmlBody || "";
  const selectedMessageHtmlDoc = useMemo(() => {
    if (!selectedMessageHtml) return "";
    return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <base target="_blank" />
    <style>
      html, body {
        margin: 0;
        padding: 0;
        background: ${theme.palette.mode === "dark" ? "#0f172a" : "#ffffff"};
        color: ${theme.palette.mode === "dark" ? "#e5e7eb" : "#0f172a"};
        font-family: Arial, sans-serif;
      }
      body {
        padding: 16px;
        overflow-wrap: anywhere;
      }
      img, table {
        max-width: 100%;
      }
      pre {
        white-space: pre-wrap;
      }
      a {
        color: ${theme.palette.mode === "dark" ? "#93c5fd" : "#2563eb"};
      }
    </style>
  </head>
  <body>${selectedMessageHtml}</body>
</html>`;
  }, [selectedMessageHtml, theme.palette.mode]);

  const handleOpenMessage = useCallback(async (messageId) => {
    setSelectedMessageId(messageId);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(true);
    try {
      const response = await api.get(`/api/mail/messages/${messageId}`);
      setSelectedMessageDetail(response.data || null);
    } catch (err) {
      setSelectedMessageError(
        err?.response?.data?.detail || err?.message || "Failed to load email content."
      );
    } finally {
      setSelectedMessageLoading(false);
    }
  }, []);

  const handleCloseMessage = useCallback(() => {
    setSelectedMessageId(null);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(false);
  }, []);

  const handleAskDeleteMachine = useCallback((vpsId) => {
    setMachineDeleteError("");
    setMachineDeleteTarget(vpsId);
  }, []);

  const handleCloseDeleteMachine = useCallback(() => {
    if (machineDeleteLoading) return;
    setMachineDeleteTarget(null);
    setMachineDeleteError("");
  }, [machineDeleteLoading]);

  const handleDeleteMachine = useCallback(async () => {
    if (!machineDeleteTarget) return;
    setMachineDeleteLoading(true);
    setMachineDeleteError("");
    setMachineDeleteSuccess("");
    try {
      const response = await api.delete(
        `/api/mail/machines/${encodeURIComponent(machineDeleteTarget)}`
      );
      const deletedMessages = response?.data?.deleted_messages ?? 0;
      const deletedRuns = response?.data?.deleted_runs ?? 0;
      setMachineDeleteSuccess(
        `Deleted ${machineDeleteTarget} (${formatNumber(deletedMessages)} messages, ${formatNumber(deletedRuns)} runs).`
      );
      setMachineDeleteTarget(null);
      setFilters((current) =>
        current.vpsId === machineDeleteTarget
          ? { ...current, vpsId: "", accountEmail: "", mailbox: "" }
          : current
      );
      await loadData();
    } catch (err) {
      setMachineDeleteError(
        err?.response?.data?.detail || err?.message || "Failed to delete machine."
      );
    } finally {
      setMachineDeleteLoading(false);
    }
  }, [loadData, machineDeleteTarget]);

  return (
    <Box>
      <Stack
        direction={{ xs: "column", lg: "row" }}
        justifyContent="flex-end"
        alignItems="center"
        mb={2}
      />

      {error ? (
        <Alert severity="error" sx={{ mb: 2.5 }}>
          {error}
        </Alert>
      ) : null}

      <Paper
        elevation={0}
        sx={{
          mb: 1.5,
          p: 0.7,
          borderRadius: "18px",
          border: `1px solid ${isDark ? alpha("#94a3b8", 0.1) : alpha("#cbd5e1", 0.3)}`,
          background: isDark
            ? "linear-gradient(180deg, rgba(30,41,59,0.3) 0%, rgba(15,23,42,0.4) 100%)"
            : "linear-gradient(180deg, rgba(255,255,255,0.7) 0%, rgba(241,245,249,0.73) 100%)",
          backdropFilter: "blur(12px)",
          boxShadow: isDark
            ? "0 4px 20px rgba(0,0,0,0.25)"
            : "0 4px 16px rgba(148,163,184,0.12)",
        }}
      >
        <Tabs
          value={activeTab}
          onChange={(_, value) => setActiveTab(value)}
          variant="fullWidth"
          sx={{
            minHeight: 0,

            "& .MuiTabs-flexContainer": {
              gap: 0.75,
            },
            "& .MuiTabs-indicator": {
              height: "100%",
              borderRadius: "14px",
              backgroundColor: isDark ? alpha("#3b82f6", 0.22) : "#ffffff",
              border: `1px solid ${isDark ? alpha("#60a5fa", 0.4) : alpha("#cbd5e1", 0.4)}`,
              boxShadow: isDark
                ? "0 4px 12px rgba(0,0,0,0.2)"
                : "0 4px 10px rgba(148,163,184,0.15)",
              zIndex: 0,
            },
            "& .MuiTab-root": {
              textTransform: "none",
              fontWeight: 700,
              fontSize: "0.88rem",
              minHeight: 46,
              borderRadius: "14px",
              color: isDark ? alpha("#94a3b8", 0.8) : alpha("#475569", 0.85),
              zIndex: 1,
              transition: "all 0.24s cubic-bezier(0.4, 0, 0.2, 1)",
              "&:hover": {
                color: isDark ? "#ffffff" : "#0f172a",
                bgcolor: alpha(isDark ? "#ffffff" : "#94a3b8", 0.05),
              },
            },
            "& .MuiTab-root.Mui-selected": {
              color: isDark ? "#60a5fa" : "#0f172a",
              fontWeight: 800,
            },
          }}
        >
          <Tab label="Mailbox" value="messages" />
          <Tab label="Setup" value="setup" />
        </Tabs>
      </Paper>

      {activeTab === "messages" ? (
        <Box
          display="grid"
          gridTemplateColumns={{ xs: "1fr", md: "repeat(3, minmax(0, 1fr))" }}
          gap={2}
          mb={2.5}
        >
          <StatCard
            icon={<DnsRoundedIcon />}
            label="Machines"
            value={formatNumber(summary.vps_count)}
            accent="#38bdf8"
          />
          <StatCard
            icon={<MailOutlineRoundedIcon />}
            label="Accounts"
            value={formatNumber(summary.account_count)}
            accent="#a78bfa"
          />
          <StatCard
            icon={<StorageRoundedIcon />}
            label="Messages"
            value={formatNumber(summary.total_messages)}
            accent="#22c55e"
          />
        </Box>
      ) : null}

      {activeTab === "messages" ? (
        <>
          <Paper
            sx={{
              p: { xs: 1.5, md: 1.75 },
              borderRadius: 3,
              mb: 2,
              border: "1px solid",
              borderColor:
                theme.palette.mode === "dark"
                  ? "rgba(148,163,184,0.22)"
                  : "rgba(15,23,42,0.12)",
              background: filterPanelBg,
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0 14px 28px rgba(15,23,42,0.34)"
                  : "0 12px 24px rgba(148,163,184,0.18)",
            }}
          >
            <Stack direction={{ xs: "column", md: "row" }} spacing={1.25} useFlexGap flexWrap="wrap">
              <FormControl size="small" sx={{ minWidth: { xs: "100%", md: 180 }, flex: 1 }}>
                <InputLabel>Machine</InputLabel>
                <Select
                  label="Machine"
                  value={filters.vpsId}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      vpsId: event.target.value,
                      accountEmail:
                        current.accountEmail &&
                        !accountOptions.includes(current.accountEmail) &&
                        event.target.value !== current.vpsId
                          ? ""
                          : current.accountEmail,
                      mailbox:
                        current.mailbox &&
                        !mailboxOptions.includes(current.mailbox) &&
                        event.target.value !== current.vpsId
                          ? ""
                          : current.mailbox,
                    }))
                  }
                >
                  <MenuItem value="">All Machines</MenuItem>
                  {vpsOptions.map((value) => (
                    <MenuItem key={value} value={value}>
                      {value}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: { xs: "100%", md: 240 }, flex: 1 }}>
                <InputLabel>Account</InputLabel>
                <Select
                  label="Account"
                  value={filters.accountEmail}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      accountEmail: event.target.value,
                    }))
                  }
                >
                  <MenuItem value="">All Accounts</MenuItem>
                  {accountOptions.map((value) => (
                    <MenuItem key={value} value={value}>
                      {value}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: { xs: "100%", md: 150 } }}>
                <InputLabel>Status</InputLabel>
                <Select
                  label="Status"
                  value={filters.status}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, status: event.target.value }))
                  }
                >
                  <MenuItem value="">All Status</MenuItem>
                  <MenuItem value="received">received</MenuItem>
                  <MenuItem value="matched">matched</MenuItem>
                  <MenuItem value="error">error</MenuItem>
                </Select>
              </FormControl>

              <TextField
                size="small"
                label="Search"
                placeholder="Subject, sender..."
                value={filters.search}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, search: event.target.value }))
                }
                sx={{ minWidth: { xs: "100%", md: 260 }, flex: 1.15 }}
              />
            </Stack>
          </Paper>

          <TableContainer
            component={Paper}
            sx={tablePaperSx}
          >
            <Table size="small">
              <TableHead sx={tableHeadSx}>
                <TableRow>
                  <TableCell>Machine</TableCell>
                  <TableCell>Account</TableCell>
                  <TableCell>From</TableCell>
                  <TableCell>Subject</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Received</TableCell>
                  <TableCell>Last Seen</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {messageItems.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      No messages found for the current filters.
                    </TableCell>
                  </TableRow>
                ) : (
                  messageItems.map((item) => (
                    <TableRow
                      key={item.id}
                      hover
                      onClick={() => handleOpenMessage(item.id)}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell>{item.vps_id || "-"}</TableCell>
                      <TableCell>{item.account_email || "-"}</TableCell>
                      <TableCell>
                        <Typography>{item.from_name || item.from_email || "-"}</Typography>
                        {item.from_name && item.from_email ? (
                          <Typography variant="body2" sx={{ opacity: 0.72 }}>
                            {item.from_email}
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell sx={{ minWidth: 280 }}>
                        <Typography fontWeight={700}>{item.subject || "(no subject)"}</Typography>
                      <Typography variant="body2" sx={{ opacity: 0.72 }}>
                          {truncatePreviewText(item.snippet)}
                      </Typography>
                    </TableCell>
                      <TableCell>
                        <Chip
                          size="small"
                          label={item.status || "unknown"}
                          color={statusChipColor(item.status)}
                          variant={item.seen ? "outlined" : "filled"}
                        />
                      </TableCell>
                      <TableCell>{formatDateTime(item.received_at)}</TableCell>
                      <TableCell>{formatDateTime(item.last_seen_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
            <TablePagination
              component="div"
              count={Number(messages?.total || 0)}
              page={mailPage}
              onPageChange={(_, nextPage) => setMailPage(nextPage)}
              rowsPerPage={MAILS_PER_PAGE}
              rowsPerPageOptions={[MAILS_PER_PAGE]}
              labelRowsPerPage="Mails per page"
              sx={{
                borderTop: "1px solid",
                borderColor:
                  theme.palette.mode === "dark"
                    ? "rgba(148,163,184,0.12)"
                    : "rgba(148,163,184,0.18)",
              }}
            />
          </TableContainer>
        </>
      ) : (
        <>
          <Paper
            sx={{
              p: { xs: 1.5, md: 1.75 },
              borderRadius: 3,
              mb: 2,
              border: "1px solid",
              borderColor:
                theme.palette.mode === "dark"
                  ? "rgba(148,163,184,0.22)"
                  : "rgba(15,23,42,0.12)",
              background: filterPanelBg,
              boxShadow:
                theme.palette.mode === "dark"
                  ? "0 14px 28px rgba(15,23,42,0.34)"
                  : "0 12px 24px rgba(148,163,184,0.18)",
            }}
          >
            {machineDeleteSuccess ? (
              <Alert severity="success" sx={{ mb: 2 }}>
                {machineDeleteSuccess}
              </Alert>
            ) : null}

            <Typography variant="h6" fontWeight={800} sx={{ mb: 2 }}>
              Add Mail
            </Typography>
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2" fontWeight={700}>
                  Gmail setup
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  Mail: enter one or more full Gmail addresses you want this machine to check, for example
                  {" "}
                  <strong>yourmail@gmail.com</strong>.
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  IMAP Password: do not use your normal Gmail password. Use a Google App Password.
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  1. Open
                  {" "}
                  <Link
                    href={GMAIL_APP_PASSWORD_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    underline="always"
                    sx={{
                      color: "#1d4ed8",
                      fontWeight: 700,
                      textUnderlineOffset: 3,
                    }}
                  >
                    Google App Passwords
                  </Link>
                </Typography>
                <Typography variant="body2">2. Sign in and create a new App Password for Mail.</Typography>
                <Typography variant="body2">
                  3. Paste that generated 16-character password into the IMAP Password field for each email below.
                </Typography>
              </Alert>

              <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} mt={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Name"
                  value={agentForm.vpsName}
                  onChange={(event) =>
                    setAgentForm((current) => ({
                      ...current,
                      vpsName: event.target.value,
                    }))
                  }
                />
              </Stack>

              <Stack spacing={1.5} mt={2}>
                {agentForm.accounts.map((account, index) => (
                  <Stack key={`agent-account-${index}`} direction={{ xs: "column", md: "row" }} spacing={1.5}>
                    <TextField
                      fullWidth
                      size="small"
                      label={`Email ${index + 1}`}
                      placeholder="Email"
                      value={account.email}
                      onChange={(event) => handleAgentAccountChange(index, "email", event.target.value)}
                    />

                    <TextField
                      fullWidth
                      size="small"
                      label={`IMAP Password ${index + 1}`}
                      type="password"
                      value={account.password}
                      onChange={(event) => handleAgentAccountChange(index, "password", event.target.value)}
                      error={
                        account.password.length > 0 &&
                        normalizeImapPassword(account.password).length < MIN_IMAP_PASSWORD_LENGTH
                      }
                      inputProps={{ minLength: MIN_IMAP_PASSWORD_LENGTH }}
                      helperText={
                        account.password.length > 0 &&
                        normalizeImapPassword(account.password).length < MIN_IMAP_PASSWORD_LENGTH
                          ? `Minimum ${MIN_IMAP_PASSWORD_LENGTH} characters`
                          : ""
                      }
                    />

                    <Button
                      variant="text"
                      color="error"
                      disabled={agentForm.accounts.length <= 1}
                      onClick={() => handleRemoveAgentAccount(index)}
                      sx={{ minWidth: { md: 120 }, textTransform: "none", fontWeight: 700 }}
                    >
                      Remove
                    </Button>
                  </Stack>
                ))}
              </Stack>

              <Box
                sx={{
                  mt: 2,
                  display: "flex",
                  gap: 1.5,
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                }}
              >
                <Button
                  variant="outlined"
                  color="primary"
                  onClick={handleAddAgentAccount}
                  sx={{ textTransform: "none", fontWeight: 700 }}
                >
                  Add Email
                </Button>

                <Button
                  variant="contained"
                  color="success"
                  onClick={handleAgentDownload}
                  disabled={agentDownload.loading}
                  sx={{
                    minWidth: { md: 220 },
                    ml: { xs: 0, md: "auto" },
                    textTransform: "none",
                    fontWeight: 700,
                  }}
                >
                  {agentDownload.loading ? "Preparing..." : "Download script"}
                </Button>
              </Box>

              {agentDownload.error ? (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {agentDownload.error}
                </Alert>
              ) : null}

              {agentDownload.success ? (
                <Alert severity="success" sx={{ mt: 2 }}>
                  {agentDownload.success}
                </Alert>
              ) : null}
          </Paper>

          <Box mb={2.5}>
            <TableContainer
              component={Paper}
              sx={tablePaperSx}
            >
              <Table size="small">
                <TableHead sx={tableHeadSx}>
                  <TableRow>
                    <TableCell>Machine</TableCell>
                    <TableCell>Account</TableCell>
                    <TableCell>Mailbox</TableCell>
                    <TableCell align="right">Messages</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Last Run</TableCell>
                    <TableCell align="center">Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {overviewItems.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} align="center">
                        No mailbox data yet.
                      </TableCell>
                    </TableRow>
                  ) : (
                    overviewItems.map((item, index) => (
                      <TableRow key={`${item.vps_id || "machine"}-${item.account_email || "account"}-${item.mailbox || "mailbox"}-${index}`} hover>
                        <TableCell>{item.vps_id || "-"}</TableCell>
                        <TableCell>{item.account_email || "-"}</TableCell>
                        <TableCell>{item.mailbox || "-"}</TableCell>
                        <TableCell align="right">{formatNumber(item.total_messages)}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={item.last_run_status || "unknown"}
                            color={statusChipColor(item.last_run_status)}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell>{formatDateTime(item.last_run_finished_at)}</TableCell>
                        <TableCell align="center">
                          <Button
                            size="small"
                            color="error"
                            variant="text"
                            onClick={() => handleAskDeleteMachine(item.vps_id)}
                            sx={{
                              textTransform: "none",
                              fontWeight: 700,
                              minWidth: 0,
                              px: 1,
                            }}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </>
      )}

      <Dialog
        open={Boolean(machineDeleteTarget)}
        onClose={handleCloseDeleteMachine}
        fullWidth
        maxWidth="xs"
        PaperProps={{
          sx: {
            borderRadius: 3,
            bgcolor: isDark ? "#1e293b" : "#ffffff",
            backgroundImage: "none",
            boxShadow: isDark ? "0 20px 50px rgba(0,0,0,0.5)" : "0 10px 30px rgba(0,0,0,0.1)",
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 800, pt: 3 }}>Confirm Delete</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: isDark ? "#94a3b8" : "text.secondary" }}>
            This will delete all messages and sync runs for{" "}
            <Box component="span" sx={{ color: isDark ? "#f8fafc" : "#1e293b", fontWeight: 700 }}>
              {machineDeleteTarget || "-"}
            </Box>
            . This action cannot be undone.
          </Typography>
          {machineDeleteError ? (
            <Alert severity="error" sx={{ mt: 2 }}>
              {machineDeleteError}
            </Alert>
          ) : null}
        </DialogContent>
        <DialogActions sx={{ p: 3, pt: 1 }}>
          <Button
            onClick={handleCloseDeleteMachine}
            disabled={machineDeleteLoading}
            sx={{
              color: isDark ? "#94a3b8" : "text.secondary",
              textTransform: "none",
              fontWeight: 700,
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteMachine}
            disabled={machineDeleteLoading}
            sx={{
              borderRadius: 2,
              textTransform: "none",
              fontWeight: 700,
              px: 3,
              boxShadow: `0 4px 12px ${alpha(theme.palette.error.main, 0.3)}`,
              "&:hover": {
                bgcolor: theme.palette.error.main,
                boxShadow: `0 6px 16px ${alpha(theme.palette.error.main, 0.4)}`,
              },
            }}
          >
            {machineDeleteLoading ? "Deleting..." : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(selectedMessageId)}
        onClose={handleCloseMessage}
        fullWidth
        maxWidth="lg"
        PaperProps={{
          sx: {
            width: "min(1200px, calc(100vw - 32px))",
            maxWidth: "1200px",
          },
        }}
      >
        <DialogTitle sx={{ pb: 1.25 }}>
          <Typography variant="h6" fontWeight={800}>
            {selectedMessageDetail?.subject || "Email content"}
          </Typography>
          <Box
            sx={{
              mt: 0.5,
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              flexWrap: "wrap",
              color: "text.secondary",
            }}
          >
            <Typography variant="body2">
              {selectedMessageDetail?.from_name || selectedMessageDetail?.from_email || "-"}
            </Typography>
            <EastRoundedIcon sx={{ fontSize: 16, opacity: 0.8 }} />
            <Typography variant="body2">
              {selectedMessageDetail?.to_email || selectedMessageDetail?.mailbox || "-"}
            </Typography>
            <Box
              component="span"
              sx={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 18,
                lineHeight: 1,
                opacity: 0.72,
                transform: "translateY(-1px)",
              }}
            >
              •
            </Box>
            <Typography variant="body2">
              {formatDateTime(selectedMessageDetail?.received_at)}
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          {selectedMessageLoading ? (
            <Box sx={{ p: 2.5 }}>
              <Typography>Loading email content...</Typography>
            </Box>
          ) : selectedMessageError ? (
            <Box sx={{ p: 2.5 }}>
              <Alert severity="error">{selectedMessageError}</Alert>
            </Box>
          ) : (
            <Stack spacing={2} sx={{ p: 2.5 }}>
              <Box>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    overflow: "hidden",
                    bgcolor:
                      theme.palette.mode === "dark"
                        ? "rgba(15,23,42,0.78)"
                        : "rgba(248,250,252,0.95)",
                  }}
                >
                  {selectedMessageHtml ? (
                    <Box
                      component="iframe"
                      title={`email-preview-${selectedMessageDetail?.id || "message"}`}
                      srcDoc={selectedMessageHtmlDoc}
                      sandbox="allow-popups allow-popups-to-escape-sandbox"
                      sx={{
                        width: "100%",
                        minHeight: 620,
                        border: 0,
                        bgcolor: theme.palette.mode === "dark" ? "#0f172a" : "#ffffff",
                      }}
                    />
                  ) : (
                    <Typography
                      component="pre"
                      sx={{
                        m: 0,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        fontFamily: "inherit",
                        fontSize: "0.92rem",
                        lineHeight: 1.65,
                      }}
                    >
                      {selectedMessageBody || "This email does not have a stored full body yet."}
                    </Typography>
                  )}
                </Paper>
              </Box>

              {!selectedMessageBody && selectedMessageDetail?.snippet ? (
                <Alert severity="info">
                  This message was ingested before full-body capture was enabled. Only preview text is available.
                </Alert>
              ) : null}
            </Stack>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};


export default MailMonitor;
