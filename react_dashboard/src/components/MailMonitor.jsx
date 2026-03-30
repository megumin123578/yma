import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
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
import ErrorOutlineRoundedIcon from "@mui/icons-material/ErrorOutlineRounded";

import api from "../services/api";


const GMAIL_APP_PASSWORD_URL =
  "https://myaccount.google.com/apppasswords?continue=https://myaccount.google.com/security?gar%3DWzI4MV0%26hl%3Den%26authuser%3D0%26rapt%3DAEjHL4N2ZCtAmejTdU1B_yLRBSQnTW3O6JdoCcy_hZd5VFQzhI2gY0vZI-IjGq30JdDYz57LMBB5uwe6ZCrFNgpcD7rGfEHV3CNkKI8o94iA6RkjdDQqOTc%26utm_source%3DOGB%26utm_medium%3Dact&pli=1&rapt=AEjHL4Oinn7oeWvsu4jswaDQ7qheJeXNrGod1MqSnOUr7oddM7BsZhOvfUP0GgK7cWjdMMO-Pdf7HXGruTKrMoeQRRX6Dqv2boAljUWm9XPLJBm_cy9Ly8k";


const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};


const formatNumber = (value) => {
  return Number(value || 0).toLocaleString();
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
  const [overview, setOverview] = useState({ summary: {}, items: [] });
  const [messages, setMessages] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({
    vpsId: "",
    mailbox: "",
    status: "",
    search: "",
  });
  const [error, setError] = useState("");
  const [autoRefresh] = useState(true);
  const [agentForm, setAgentForm] = useState({
    vpsName: "",
    username: "",
    password: "",
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
          .map((item) => item.mailbox)
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
            mailbox: filters.mailbox || undefined,
            status: filters.status || undefined,
            search: filters.search || undefined,
            limit: 100,
          },
        }),
      ]);
      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load email manager data.");
    }
  }, [filters.mailbox, filters.search, filters.status, filters.vpsId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => {
      loadData();
    }, 45000);
    return () => window.clearInterval(timer);
  }, [autoRefresh, loadData]);

  const handleAgentDownload = useCallback(async () => {
    const vpsName = agentForm.vpsName.trim();
    const username = agentForm.username.trim();
    const password = agentForm.password;
    if (!vpsName || !username || !password) {
      setAgentDownload({
        loading: false,
        error: "Name, username, and password are required.",
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
          username,
          password,
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
        password: "",
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
  }, [agentForm.password, agentForm.username, agentForm.vpsName]);

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
          gridTemplateColumns={{ xs: "1fr", md: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" }}
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
            label="Mailboxes"
            value={formatNumber(summary.mailbox_count)}
            accent="#a78bfa"
          />
          <StatCard
            icon={<StorageRoundedIcon />}
            label="Messages"
            value={formatNumber(summary.total_messages)}
            accent="#22c55e"
          />
          <StatCard
            icon={<ErrorOutlineRoundedIcon />}
            label="Unread / Error"
            value={`${formatNumber(summary.unread_messages)} / ${formatNumber(summary.error_messages)}`}
            accent="#f97316"
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

              <FormControl size="small" sx={{ minWidth: { xs: "100%", md: 220 }, flex: 1 }}>
                <InputLabel>Mailbox</InputLabel>
                <Select
                  label="Mailbox"
                  value={filters.mailbox}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, mailbox: event.target.value }))
                  }
                >
                  <MenuItem value="">All Mailboxes</MenuItem>
                  {mailboxOptions.map((value) => (
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
                  <TableCell>Mailbox</TableCell>
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
                    <TableCell colSpan={6} align="center">
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
                      <TableCell>
                        <Typography fontWeight={700}>{item.vps_id || "-"}</Typography>
                        <Typography variant="body2" sx={{ opacity: 0.72 }}>
                          {item.mailbox || "-"}
                        </Typography>
                      </TableCell>
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
                          {item.snippet || "-"}
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
            <Typography variant="h6" fontWeight={800} sx={{ mb: 2 }}>
              Add Mail
            </Typography>
              <Alert severity="info" sx={{ mt: 2 }}>
                <Typography variant="body2" fontWeight={700}>
                  Gmail setup
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                  Mail: enter the full Gmail address you want this machine to check, for example
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
                <Typography variant="body2">3. Paste that generated password into the IMAP Password field below.</Typography>
              </Alert>

              <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} mt={2}>
                <TextField
                  fullWidth
                  size="small"
                  label="Name"
                  placeholder="machine-hcm-01"
                  value={agentForm.vpsName}
                  onChange={(event) =>
                    setAgentForm((current) => ({
                      ...current,
                      vpsName: event.target.value,
                    }))
                  }
                />

                <TextField
                  fullWidth
                  size="small"
                  label="Email"
                  placeholder="Email"
                  value={agentForm.username}
                  onChange={(event) =>
                    setAgentForm((current) => ({
                      ...current,
                      username: event.target.value,
                    }))
                  }
                />

                <TextField
                  fullWidth
                  size="small"
                  label="IMAP Password"
                  type="password"
                  value={agentForm.password}
                  onChange={(event) =>
                    setAgentForm((current) => ({
                      ...current,
                      password: event.target.value,
                    }))
                  }
                />

                <Button
                  variant="contained"
                  color="success"
                  onClick={handleAgentDownload}
                  disabled={agentDownload.loading}
                  sx={{ minWidth: { md: 220 }, textTransform: "none", fontWeight: 700 }}
                >
                  {agentDownload.loading ? "Preparing..." : "Download script"}
                </Button>
              </Stack>

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
                    <TableCell>Mailbox</TableCell>
                    <TableCell align="right">Messages</TableCell>
                    <TableCell align="right">Unread</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Inserted</TableCell>
                    <TableCell align="right">Updated</TableCell>
                    <TableCell>Last Run</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {overviewItems.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} align="center">
                        No mailbox data yet.
                      </TableCell>
                    </TableRow>
                  ) : (
                    overviewItems.map((item, index) => (
                      <TableRow key={`${item.vps_id || "vps"}-${item.mailbox || "mailbox"}-${index}`} hover>
                        <TableCell>{item.vps_id || "-"}</TableCell>
                        <TableCell>{item.mailbox || "-"}</TableCell>
                        <TableCell align="right">{formatNumber(item.total_messages)}</TableCell>
                        <TableCell align="right">{formatNumber(item.unread_messages)}</TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            label={item.last_run_status || "unknown"}
                            color={statusChipColor(item.last_run_status)}
                            variant="outlined"
                          />
                        </TableCell>
                        <TableCell align="right">
                          {formatNumber(item.last_run_inserted_count)}
                        </TableCell>
                        <TableCell align="right">
                          {formatNumber(item.last_run_updated_count)}
                        </TableCell>
                        <TableCell>{formatDateTime(item.last_run_finished_at)}</TableCell>
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
        open={Boolean(selectedMessageId)}
        onClose={handleCloseMessage}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle sx={{ pb: 1.25 }}>
          <Typography variant="h6" fontWeight={800}>
            {selectedMessageDetail?.subject || "Email content"}
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5, color: "text.secondary" }}>
            {selectedMessageDetail?.from_name || selectedMessageDetail?.from_email || "-"}
            {" -> "}
            {selectedMessageDetail?.to_email || selectedMessageDetail?.mailbox || "-"}
            {" • "}
            {formatDateTime(selectedMessageDetail?.received_at)}
          </Typography>
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
                <Typography variant="body2" fontWeight={700} sx={{ mb: 0.75 }}>
                  Full content
                </Typography>
                <Paper
                  variant="outlined"
                  sx={{
                    p: 1.5,
                    borderRadius: 2,
                    bgcolor:
                      theme.palette.mode === "dark"
                        ? "rgba(15,23,42,0.78)"
                        : "rgba(248,250,252,0.95)",
                  }}
                >
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
                </Paper>
              </Box>

              {!selectedMessageBody && selectedMessageDetail?.snippet ? (
                <Alert severity="info">
                  This message was ingested before full-body capture was enabled. Only preview text is available.
                </Alert>
              ) : null}

              {selectedMessageHtml ? (
                <Box>
                  <Typography variant="body2" fontWeight={700} sx={{ mb: 0.75 }}>
                    HTML source
                  </Typography>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      borderRadius: 2,
                      maxHeight: 220,
                      overflow: "auto",
                      bgcolor:
                        theme.palette.mode === "dark"
                          ? "rgba(15,23,42,0.62)"
                          : "rgba(248,250,252,0.88)",
                    }}
                  >
                    <Typography
                      component="pre"
                      sx={{
                        m: 0,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                        fontSize: "0.78rem",
                        lineHeight: 1.5,
                      }}
                    >
                      {selectedMessageHtml}
                    </Typography>
                  </Paper>
                </Box>
              ) : null}
            </Stack>
          )}
        </DialogContent>
      </Dialog>
    </Box>
  );
};


export default MailMonitor;
