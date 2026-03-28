import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  FormControl,
  InputLabel,
  Link,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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
        p: 2.2,
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
        minHeight: 132,
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
          <Typography variant="h3" fontWeight={800} mt={1} color="text.primary">
            {value}
          </Typography>
        </Box>
        <Box
          sx={{
            width: 42,
            height: 42,
            borderRadius: 2.5,
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
  const [overview, setOverview] = useState({ summary: {}, items: [] });
  const [messages, setMessages] = useState({ items: [], total: 0 });
  const [runs, setRuns] = useState({ items: [] });
  const [filters, setFilters] = useState({
    vpsId: "",
    mailbox: "",
    status: "",
    search: "",
  });
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [agentForm, setAgentForm] = useState({
    username: "",
    password: "",
  });
  const [agentDownload, setAgentDownload] = useState({
    loading: false,
    error: "",
    success: "",
  });
  const [agentVpsSeed, setAgentVpsSeed] = useState("");
  const [showAddMail, setShowAddMail] = useState(false);

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

  const nextVpsFromOverview = useMemo(() => {
    let maxSuffix = 0;
    overviewItems.forEach((item) => {
      const match = String(item?.vps_id || "").match(/^vps-(\d+)$/i);
      if (!match) return;
      maxSuffix = Math.max(maxSuffix, Number(match[1] || 0));
    });
    return `vps-${String(maxSuffix + 1).padStart(2, "0")}`;
  }, [overviewItems]);

  const nextVpsPreview = agentVpsSeed || nextVpsFromOverview;

  const runItems = useMemo(
    () =>
      (Array.isArray(runs?.items) ? runs.items : []).filter(
        (item) => item && typeof item === "object"
      ),
    [runs]
  );

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
      const [overviewResp, messagesResp, runsResp] = await Promise.all([
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
        api.get("/api/mail/runs", {
          params: {
            vps_id: filters.vpsId || undefined,
            mailbox: filters.mailbox || undefined,
            limit: 30,
          },
        }),
      ]);
      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
      setRuns(runsResp.data || { items: [] });
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
    const username = agentForm.username.trim();
    const password = agentForm.password;
    if (!username || !password) {
      setAgentDownload({
        loading: false,
        error: "Username and password are required.",
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
          username,
          password,
        },
        {
          responseType: "blob",
        }
      );

      const contentDisposition = response.headers?.["content-disposition"] || "";
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      const filename = filenameMatch?.[1] || "main_agent.py";
      const vpsId = response.headers?.["x-agent-vps-id"] || nextVpsPreview;

      const blob = new Blob([response.data], {
        type: response.headers?.["content-type"] || "text/x-python",
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
      const nextMatch = String(vpsId).match(/^vps-(\d+)$/i);
      if (nextMatch) {
        const nextSuffix = Number(nextMatch[1] || 0) + 1;
        setAgentVpsSeed(`vps-${String(nextSuffix).padStart(2, "0")}`);
      }
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
  }, [agentForm.password, agentForm.username, nextVpsPreview]);

  useEffect(() => {
    if (!agentVpsSeed) return;
    const issuedMatch = String(agentVpsSeed).match(/^vps-(\d+)$/i);
    const overviewMatch = String(nextVpsFromOverview).match(/^vps-(\d+)$/i);
    if (!issuedMatch || !overviewMatch) return;
    if (Number(issuedMatch[1] || 0) <= Number(overviewMatch[1] || 0)) {
      setAgentVpsSeed("");
    }
  }, [agentVpsSeed, nextVpsFromOverview]);

  const summary = overview?.summary || {};
  const filterPanelBg =
    theme.palette.mode === "dark"
      ? "rgba(15,23,42,0.82)"
      : "rgba(255,255,255,0.94)";

  return (
    <Box m="20px">
      <Stack
        direction={{ xs: "column", lg: "row" }}
        justifyContent="space-between"
        alignItems={{ xs: "flex-start", lg: "center" }}
        spacing={2}
      >
        <Box>
          <Typography
            variant="h5"
            fontWeight={700}
            color="text.secondary"
            sx={{ letterSpacing: "0.01em" }}
          >
            Manage mail from VPS
          </Typography>
        </Box>
        <Stack direction="row" alignItems="center" spacing={1.2}>
          <Typography variant="body2" fontWeight={700}>
            Auto refresh
          </Typography>
          <Switch
            checked={autoRefresh}
            onChange={(event) => setAutoRefresh(event.target.checked)}
            color="success"
          />
        </Stack>
      </Stack>

      {error ? (
        <Alert severity="error" sx={{ mb: 2.5 }}>
          {error}
        </Alert>
      ) : null}

      <Paper
        sx={{
          p: 2,
          borderRadius: 3,
          mb: 2.5,
          border: "1px solid",
          borderColor: "divider",
          background:
            theme.palette.mode === "dark"
              ? "rgba(10,15,24,0.82)"
              : "rgba(255,255,255,0.96)",
        }}
      >
        <Stack
          direction={{ xs: "column", lg: "row" }}
          justifyContent="space-between"
          alignItems={{ xs: "flex-start", lg: "center" }}
          spacing={1.5}
        >
          <Stack direction="row" spacing={1.25} alignItems="center">
            <Button
              variant={showAddMail ? "outlined" : "contained"}
              color="success"
              onClick={() => setShowAddMail((current) => !current)}
              sx={{ textTransform: "none", fontWeight: 700 }}
            >
              {showAddMail ? "Hide" : "Add Mail"}
            </Button>
          </Stack>
          <Chip
            label={`Next VPS ID: ${nextVpsPreview}`}
            color="info"
            variant="outlined"
          />
        </Stack>

        <Collapse in={showAddMail}>
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2" fontWeight={700}>
              Gmail setup
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              Mail: enter the full Gmail address you want this VPS to check, for example
              {" "}
              <strong>yourmail@gmail.com</strong>.
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              IMAP Password: do not use your normal Gmail password. Use a Google App Password.
            </Typography>
            <Typography variant="body2" sx={{ mt: 0.5 }}>
              1. Open
              {" "}
              <Link href={GMAIL_APP_PASSWORD_URL} target="_blank" rel="noopener noreferrer">
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
              label="IMAP Username"
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
        </Collapse>
      </Paper>

      <Box
        display="grid"
        gridTemplateColumns={{ xs: "1fr", md: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" }}
        gap={2}
        mb={2.5}
      >
        <StatCard
          icon={<DnsRoundedIcon />}
          label="VPS"
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

      <Paper
        sx={{
          p: 2,
          borderRadius: 3,
          mb: 2.5,
          border: "1px solid",
          borderColor: "divider",
          background: filterPanelBg,
        }}
      >
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
          <FormControl fullWidth size="small">
            <InputLabel>VPS</InputLabel>
            <Select
              label="VPS"
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
              <MenuItem value="">All VPS</MenuItem>
              {vpsOptions.map((value) => (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl fullWidth size="small">
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

          <FormControl fullWidth size="small">
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
            fullWidth
            size="small"
            label="Search"
            value={filters.search}
            onChange={(event) =>
              setFilters((current) => ({ ...current, search: event.target.value }))
            }
          />
        </Stack>
      </Paper>

      <Box
        display="grid"
        gridTemplateColumns={{ xs: "1fr", xl: "minmax(0, 1.2fr) minmax(0, 0.8fr)" }}
        gap={2.5}
        mb={2.5}
      >
        <TableContainer
          component={Paper}
          sx={{
            borderRadius: 3,
            border: "1px solid",
            borderColor: "divider",
            background:
              theme.palette.mode === "dark"
                ? "rgba(10,15,24,0.82)"
                : "rgba(255,255,255,0.96)",
          }}
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>VPS</TableCell>
                <TableCell>Mailbox</TableCell>
                <TableCell align="right">Messages</TableCell>
                <TableCell align="right">Unread</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Last Run</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {overviewItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} align="center">
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
                    <TableCell>{formatDateTime(item.last_run_finished_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <TableContainer
          component={Paper}
          sx={{
            borderRadius: 3,
            border: "1px solid",
            borderColor: "divider",
            background:
              theme.palette.mode === "dark"
                ? "rgba(10,15,24,0.82)"
                : "rgba(255,255,255,0.96)",
          }}
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Run</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Inserted</TableCell>
                <TableCell align="right">Updated</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {runItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center">
                    No recent runs.
                  </TableCell>
                </TableRow>
              ) : (
                runItems.map((item) => (
                  <TableRow key={item.id} hover>
                    <TableCell>
                      <Typography fontWeight={700}>{item.vps_id || "-"}</Typography>
                      <Typography variant="body2" sx={{ opacity: 0.72 }}>
                        {item.mailbox || "-"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={item.status || "unknown"}
                        color={statusChipColor(item.status)}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="right">{formatNumber(item.inserted_count)}</TableCell>
                    <TableCell align="right">{formatNumber(item.updated_count)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>

      <TableContainer
        component={Paper}
        sx={{
          borderRadius: 3,
          border: "1px solid",
          borderColor: "divider",
          background:
            theme.palette.mode === "dark"
              ? "rgba(10,15,24,0.82)"
              : "rgba(255,255,255,0.96)",
        }}
      >
        <Table size="small">
          <TableHead>
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
                <TableRow key={item.id} hover>
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
    </Box>
  );
};


export default MailMonitor;
