import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  ListItemText,
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
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteOutlineRoundedIcon from "@mui/icons-material/DeleteOutlineRounded";
import EastRoundedIcon from "@mui/icons-material/EastRounded";
import SyncRoundedIcon from "@mui/icons-material/SyncRounded";
import { useSearchParams } from "react-router-dom";

import api from "../services/api";
import { UserContext } from "../context/UserContext";

const MAILS_PER_PAGE = 50;
const MAIL_OAUTH_POLL_MS = 2000;
const MAIL_LABEL_OPTIONS = [
  { value: "INBOX", label: "Inbox" },
  { value: "CATEGORY_UPDATES", label: "Updates" },
  { value: "CATEGORY_PROMOTIONS", label: "Promotions" },
  { value: "CATEGORY_SOCIAL", label: "Social" },
  { value: "CATEGORY_FORUMS", label: "Forums" },
];

const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
};

const formatNumber = (value) => Number(value || 0).toLocaleString();

const normalizeLabelIds = (value) => {
  const labels = Array.isArray(value) ? value : String(value || "").split(",");
  return labels.map((item) => String(item || "").trim()).filter(Boolean);
};

const formatLabelSelection = (values) => {
  const selected = normalizeLabelIds(values);
  if (!selected.length) return "None";
  const labelMap = new Map(MAIL_LABEL_OPTIONS.map((item) => [item.value, item.label]));
  return selected.map((value) => labelMap.get(value) || value).join(", ");
};

const decodeHtmlEntities = (value) => {
  if (!value || typeof window === "undefined") return value || "";
  const textarea = document.createElement("textarea");
  textarea.innerHTML = value;
  return textarea.value;
};

const truncatePreviewText = (value, maxLength = 90) => {
  const raw = decodeHtmlEntities(String(value || ""))
    .replace(/<[^>]*>/g, " ")
    .replace(/\[(?:image|cid:[^\]]+|attachment|logo)[^\]]*\]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!raw) return "-";
  if (raw.length <= maxLength) return raw;
  return `${raw.slice(0, maxLength).trimEnd()}...`;
};

const statusChipColor = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "error") return "error";
  if (normalized === "ok" || normalized === "completed") return "success";
  if (normalized === "matched") return "info";
  if (normalized === "pending") return "warning";
  return "default";
};

const greenOutlinedButtonSx = {
  borderColor: "secondary.main",
  color: "secondary.main",
  backgroundColor: "rgba(76, 206, 172, 0.08)",
  "&:hover": {
    borderColor: "secondary.main",
    backgroundColor: "rgba(76, 206, 172, 0.16)",
  },
  "&.Mui-disabled": {
    borderColor: "rgba(148, 163, 184, 0.35)",
    color: "text.disabled",
  },
};

const greenContainedButtonSx = {
  backgroundColor: "secondary.main",
  color: "#04140f",
  "&:hover": {
    backgroundColor: "secondary.main",
    filter: "brightness(0.92)",
  },
  "&.Mui-disabled": {
    backgroundColor: "rgba(148, 163, 184, 0.24)",
    color: "text.disabled",
  },
};

const greenIconButtonSx = {
  border: "1px solid",
  borderColor: "secondary.main",
  color: "secondary.main",
  backgroundColor: "rgba(76, 206, 172, 0.08)",
  borderRadius: 1,
  "&:hover": {
    backgroundColor: "rgba(76, 206, 172, 0.16)",
  },
  "&.Mui-disabled": {
    borderColor: "rgba(148, 163, 184, 0.35)",
    color: "text.disabled",
  },
};

const redIconButtonSx = {
  border: "1px solid",
  borderColor: "error.main",
  color: "error.main",
  backgroundColor: "rgba(219, 79, 74, 0.08)",
  borderRadius: 1,
  "&:hover": {
    backgroundColor: "rgba(219, 79, 74, 0.16)",
  },
  "&.Mui-disabled": {
    borderColor: "rgba(148, 163, 184, 0.35)",
    color: "text.disabled",
  },
};

const greenCheckboxSx = {
  color: "secondary.main",
  "&.Mui-checked": {
    color: "secondary.main",
  },
};

const MailMonitor = () => {
  const { user, loading } = useContext(UserContext);
  const isAdmin = !!user?.is_admin;
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(() =>
    searchParams.get("tab") === "accounts" ? "accounts" : "messages"
  );

  const [overview, setOverview] = useState({ summary: {}, items: [] });
  const [messages, setMessages] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({
    accountEmail: "",
    mailbox: "",
    status: "matched",
    search: "",
  });
  const [mailPage, setMailPage] = useState(0);
  const [error, setError] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [selectedMessageDetail, setSelectedMessageDetail] = useState(null);
  const [selectedMessageLoading, setSelectedMessageLoading] = useState(false);
  const [selectedMessageError, setSelectedMessageError] = useState("");
  const [mailAccessDenied, setMailAccessDenied] = useState(false);
  const [mailAccounts, setMailAccounts] = useState([]);
  const [mailOAuthState, setMailOAuthState] = useState("");
  const [mailOAuthStatus, setMailOAuthStatus] = useState({ type: "", message: "" });
  const [connectingMail, setConnectingMail] = useState(false);
  const [accountSearch, setAccountSearch] = useState("");
  const [accountActionStatus, setAccountActionStatus] = useState({ type: "", message: "" });
  const [accountActionId, setAccountActionId] = useState("");

  const overviewItems = useMemo(
    () => (Array.isArray(overview?.items) ? overview.items : []).filter(Boolean),
    [overview]
  );
  const messageItems = useMemo(
    () => (Array.isArray(messages?.items) ? messages.items : []).filter(Boolean),
    [messages]
  );
  const summary = overview?.summary || {};
  const connectedAccountCount = mailAccounts.length || Number(summary.account_count || 0);
  const filteredMailAccounts = useMemo(() => {
    const searchText = accountSearch.trim().toLowerCase();
    if (!searchText) return mailAccounts;
    return mailAccounts.filter((account) =>
      String(account?.account_email || "").toLowerCase().includes(searchText)
    );
  }, [accountSearch, mailAccounts]);

  const accountOptions = useMemo(() => {
    return [
      ...new Set(
        overviewItems
          .map((item) => item?.account_email)
          .concat(mailAccounts.map((item) => item?.account_email))
          .filter(Boolean)
      ),
    ];
  }, [mailAccounts, overviewItems]);

  const mailboxOptions = useMemo(() => {
    return [
      ...new Set(
        overviewItems
          .filter((item) => !filters.accountEmail || item.account_email === filters.accountEmail)
          .map((item) => item?.mailbox)
          .filter(Boolean)
      ),
    ];
  }, [filters.accountEmail, overviewItems]);

  const loadData = useCallback(async () => {
    if (loading || !isAdmin || mailAccessDenied) {
      setError("");
      setOverview({ summary: {}, items: [] });
      setMessages({ items: [], total: 0 });
      setMailAccounts([]);
      return;
    }

    setError("");
    try {
      const [overviewResp, messagesResp, accountsResp] = await Promise.all([
        api.get("/api/mail/overview"),
        api.get("/api/mail/messages", {
          params: {
            account_email: filters.accountEmail || undefined,
            mailbox: filters.mailbox || undefined,
            status: filters.status || undefined,
            search: filters.search || undefined,
            limit: MAILS_PER_PAGE,
            offset: mailPage * MAILS_PER_PAGE,
            per_account_limit: MAILS_PER_PAGE,
          },
        }),
        api.get("/api/mail/accounts"),
      ]);

      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
      setMailAccounts(Array.isArray(accountsResp.data?.items) ? accountsResp.data.items : []);
    } catch (err) {
      if (err?.response?.status === 403) {
        setMailAccessDenied(true);
        setOverview({ summary: {}, items: [] });
        setMessages({ items: [], total: 0 });
        setMailAccounts([]);
        setError("Admin access required.");
        return;
      }
      setError(err?.response?.data?.detail || err?.message || "Failed to load email manager data.");
    }
  }, [filters.accountEmail, filters.mailbox, filters.search, filters.status, isAdmin, loading, mailAccessDenied, mailPage]);

  const handleStartMailOAuth = useCallback(async () => {
    if (connectingMail) return;
    setConnectingMail(true);
    setMailOAuthStatus({ type: "", message: "" });
    try {
      const response = await api.post("/api/mail/accounts/oauth/start", {
        label_ids: ["INBOX"],
      });
      const nextUrl = response.data?.auth_url || "";
      const nextState = response.data?.state || "";
      setMailOAuthState(nextState);
      setMailOAuthStatus({
        type: "info",
        message: nextUrl ? "Google authorization opened." : "Gmail authorization started.",
      });
      if (nextUrl) {
        window.open(nextUrl, "_blank", "noopener");
      }
    } catch (err) {
      setMailOAuthStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to start Gmail authorization.",
      });
    } finally {
      setConnectingMail(false);
    }
  }, [connectingMail]);

  const handleTabChange = useCallback((_, nextTab) => {
    setActiveTab(nextTab);
    if (nextTab === "accounts") {
      setSelectedMessageId(null);
      setSelectedMessageDetail(null);
      setSelectedMessageError("");
      setSelectedMessageLoading(false);
    }
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      if (nextTab === "accounts") {
        nextParams.set("tab", "accounts");
        nextParams.delete("messageId");
      } else {
        nextParams.delete("tab");
      }
      return nextParams;
    }, { replace: true });
  }, [setSearchParams]);

  const handleUpdateMailAccount = useCallback(async (account, changes) => {
    if (!account?.id) return;
    const actionKey = `${account.id}:update`;
    setAccountActionId(actionKey);
    setAccountActionStatus({ type: "", message: "" });
    try {
      const response = await api.patch(`/api/mail/accounts/${account.id}`, changes);
      const updatedAccount = response.data?.account;
      if (updatedAccount) {
        setMailAccounts((current) =>
          current.map((item) => (item.id === updatedAccount.id ? updatedAccount : item))
        );
      } else {
        await loadData();
      }
    } catch (err) {
      setAccountActionStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to update Gmail account.",
      });
    } finally {
      setAccountActionId("");
    }
  }, [loadData]);

  const handleAutoSaveAccountLabels = useCallback((account, nextLabels) => {
    if (!account?.id) return;
    handleUpdateMailAccount(account, { label_ids: normalizeLabelIds(nextLabels) });
  }, [handleUpdateMailAccount]);

  const handleSyncMailAccount = useCallback(async (account) => {
    if (!account?.id) return;
    const actionKey = `${account.id}:sync`;
    setAccountActionId(actionKey);
    setAccountActionStatus({ type: "", message: "" });
    try {
      await api.post(`/api/mail/accounts/${account.id}/sync`);
      await loadData();
      setAccountActionStatus({
        type: "success",
        message: `Synced ${account.account_email || "Gmail account"}.`,
      });
    } catch (err) {
      setAccountActionStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to sync Gmail account.",
      });
    } finally {
      setAccountActionId("");
    }
  }, [loadData]);

  const handleSyncAllMailAccounts = useCallback(async () => {
    setAccountActionId("sync-all");
    setAccountActionStatus({ type: "", message: "" });
    try {
      await api.post("/api/mail/sync");
      await loadData();
      setAccountActionStatus({ type: "success", message: "Synced all accounts." });
    } catch (err) {
      setAccountActionStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to sync accounts.",
      });
    } finally {
      setAccountActionId("");
    }
  }, [loadData]);

  const handleDeleteMailAccount = useCallback(async (account) => {
    if (!account?.id) return;
    const accountLabel = account.account_email || "this Gmail account";
    if (typeof window !== "undefined" && !window.confirm(`Remove ${accountLabel}?`)) {
      return;
    }

    const actionKey = `${account.id}:delete`;
    setAccountActionId(actionKey);
    setAccountActionStatus({ type: "", message: "" });
    try {
      await api.delete(`/api/mail/accounts/${account.id}`);
      setMailAccounts((current) => current.filter((item) => item.id !== account.id));
      await loadData();
      setAccountActionStatus({ type: "success", message: `Removed ${accountLabel}.` });
    } catch (err) {
      setAccountActionStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to remove Gmail account.",
      });
    } finally {
      setAccountActionId("");
    }
  }, [loadData]);

  const handleOpenMessage = useCallback(async (messageId) => {
    setSelectedMessageId(messageId);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(true);
    try {
      const response = await api.get(`/api/mail/messages/${messageId}`);
      setSelectedMessageDetail(response.data || null);
    } catch (err) {
      setSelectedMessageError(err?.response?.data?.detail || err?.message || "Failed to load email content.");
    } finally {
      setSelectedMessageLoading(false);
    }
  }, []);

  const handleCloseMessage = useCallback(() => {
    setSelectedMessageId(null);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(false);
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      nextParams.delete("messageId");
      return nextParams;
    }, { replace: true });
  }, [setSearchParams]);

  useEffect(() => {
    if (loading || !isAdmin || mailAccessDenied) return undefined;
    loadData();
    return undefined;
  }, [isAdmin, loadData, loading, mailAccessDenied]);

  useEffect(() => {
    setMailPage(0);
  }, [filters.accountEmail, filters.mailbox, filters.status, filters.search]);

  useEffect(() => {
    if (loading || !isAdmin || mailAccessDenied) return undefined;
    const timer = window.setInterval(() => loadData(), 45000);
    return () => window.clearInterval(timer);
  }, [isAdmin, loadData, loading, mailAccessDenied]);

  useEffect(() => {
    if (!mailOAuthState || loading || !isAdmin || mailAccessDenied) return undefined;

    let stopped = false;

    const poll = async () => {
      try {
        const response = await api.get(`/api/mail/accounts/oauth/state/${encodeURIComponent(mailOAuthState)}`);
        const data = response.data || {};
        if (data.ready || data.status === "completed") {
          setMailOAuthState("");
          setMailOAuthStatus({
            type: "success",
            message: data.account_email ? `Gmail connected: ${data.account_email}` : "Gmail connected.",
          });
          await loadData();
          return true;
        }
        if (data.status === "failed" || data.status === "expired") {
          setMailOAuthState("");
          setMailOAuthStatus({
            type: "error",
            message: data.error_message || "Gmail authorization did not complete.",
          });
          return true;
        }
      } catch (err) {
        setMailOAuthState("");
        setMailOAuthStatus({
          type: "error",
          message: err?.response?.data?.detail || err?.message || "Failed to check Gmail authorization.",
        });
        return true;
      }
      return false;
    };

    const intervalId = window.setInterval(async () => {
      if (!stopped) {
        const done = await poll();
        if (done) {
          stopped = true;
          window.clearInterval(intervalId);
        }
      }
    }, MAIL_OAUTH_POLL_MS);

    poll();

    return () => {
      stopped = true;
      window.clearInterval(intervalId);
    };
  }, [isAdmin, loadData, loading, mailAccessDenied, mailOAuthState]);

  useEffect(() => {
    setMailAccessDenied(false);
    setMailOAuthState("");
    setMailOAuthStatus({ type: "", message: "" });
    setAccountActionStatus({ type: "", message: "" });
    setAccountActionId("");
  }, [user?.id, user?.username]);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (!tabParam) {
      setActiveTab("messages");
      return;
    }
    if (tabParam === "accounts" || tabParam === "messages") {
      setActiveTab(tabParam);
      return;
    }
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);
      nextParams.delete("tab");
      return nextParams;
    }, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const messageIdParam = searchParams.get("messageId");
    const normalizedMessageId = Number(messageIdParam);
    if (!messageIdParam || Number.isNaN(normalizedMessageId) || normalizedMessageId <= 0) return;
    setActiveTab("messages");
    handleOpenMessage(normalizedMessageId);
  }, [handleOpenMessage, searchParams]);

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
    return `<!doctype html><html><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><base target="_blank" /><style>html,body{margin:0;padding:0;background:#fff;color:#0f172a;font-family:Arial,sans-serif}body{padding:16px;overflow-wrap:anywhere}img,table{max-width:100%}pre{white-space:pre-wrap}a{color:#2563eb}</style></head><body>${selectedMessageHtml}</body></html>`;
  }, [selectedMessageHtml]);

  if (loading) {
    return null;
  }

  if (!isAdmin || mailAccessDenied) {
    return <Alert severity="warning">Email Manager is available to admin accounts only.</Alert>;
  }

  return (
    <Box>
      {error ? <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert> : null}
      {mailOAuthStatus.message ? (
        <Alert severity={mailOAuthStatus.type || "info"} sx={{ mb: 2 }}>
          {mailOAuthStatus.message}
        </Alert>
      ) : null}

      <Paper variant="outlined" sx={{ mb: 2, borderRadius: 2, overflow: "hidden" }}>
        <Tabs
          value={activeTab}
          onChange={handleTabChange}
          variant="scrollable"
          allowScrollButtonsMobile
          sx={{
            "& .MuiTab-root": {
              color: "#60a5fa",
              fontWeight: 700,
            },
            "& .Mui-selected": {
              color: "#60a5fa",
            },
            "& .MuiTabs-indicator": {
              backgroundColor: "#ffffff",
            },
          }}
        >
          <Tab value="messages" label="Messages" />
          <Tab value="accounts" label="Accounts" />
        </Tabs>
      </Paper>

      {activeTab === "messages" ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2} mb={2}>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
              <Typography variant="body2" color="text.secondary">Messages</Typography>
              <Typography variant="h5" fontWeight={800}>{formatNumber(summary.total_messages)}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
              <Typography variant="body2" color="text.secondary">Accounts</Typography>
              <Typography variant="h5" fontWeight={800}>{formatNumber(connectedAccountCount)}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
              <Typography variant="body2" color="text.secondary">Mailboxes</Typography>
              <Typography variant="h5" fontWeight={800}>{formatNumber(summary.mailbox_count)}</Typography>
            </Paper>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
              <Typography variant="body2" color="text.secondary">Errors</Typography>
              <Typography variant="h5" fontWeight={800}>{formatNumber(summary.error_messages)}</Typography>
            </Paper>
          </Stack>

          <Paper variant="outlined" sx={{ p: 2, mb: 2, borderRadius: 2 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={1.5}>
              <FormControl size="small" sx={{ minWidth: 220 }}>
                <InputLabel>Account</InputLabel>
                <Select
                  label="Account"
                  value={filters.accountEmail}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      accountEmail: event.target.value,
                      mailbox:
                        current.mailbox &&
                        !mailboxOptions.includes(current.mailbox) &&
                        event.target.value !== current.accountEmail
                          ? ""
                          : current.mailbox,
                    }))
                  }
                >
                  <MenuItem value="">All Accounts</MenuItem>
                  {accountOptions.map((value) => (
                    <MenuItem key={value} value={value}>{value}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel>Mailbox</InputLabel>
                <Select
                  label="Mailbox"
                  value={filters.mailbox}
                  onChange={(event) => setFilters((current) => ({ ...current, mailbox: event.target.value }))}
                >
                  <MenuItem value="">All Mailboxes</MenuItem>
                  {mailboxOptions.map((value) => (
                    <MenuItem key={value} value={value}>{value}</MenuItem>
                  ))}
                </Select>
              </FormControl>

              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>Status</InputLabel>
                <Select
                  label="Status"
                  value={filters.status}
                  onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
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
                onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
                sx={{ flex: 1 }}
              />
            </Stack>
          </Paper>

          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Account</TableCell>
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
                    <TableCell colSpan={7} align="center">No messages found for the current filters.</TableCell>
                  </TableRow>
                ) : (
                  messageItems.map((item) => (
                    <TableRow key={item.id} hover onClick={() => handleOpenMessage(item.id)} sx={{ cursor: "pointer" }}>
                      <TableCell>{item.account_email || "-"}</TableCell>
                      <TableCell>{item.mailbox || "-"}</TableCell>
                      <TableCell>
                        <Typography>{item.from_name || item.from_email || "-"}</Typography>
                        {item.from_name && item.from_email ? (
                          <Typography variant="body2" color="text.secondary">{item.from_email}</Typography>
                        ) : null}
                      </TableCell>
                      <TableCell sx={{ minWidth: 280 }}>
                        <Typography fontWeight={700}>{item.subject || "(no subject)"}</Typography>
                        <Typography variant="body2" color="text.secondary">
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
            />
          </TableContainer>
        </>
      ) : (
        <>
          {accountActionStatus.message ? (
            <Alert severity={accountActionStatus.type || "info"} sx={{ mb: 2 }}>
              {accountActionStatus.message}
            </Alert>
          ) : null}

          <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={1.5}
            justifyContent="flex-end"
            alignItems={{ xs: "stretch", md: "center" }}
            sx={{ mb: 2 }}
          >
            <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
              <TextField
                size="small"
                placeholder="Search accounts"
                value={accountSearch}
                onChange={(event) => setAccountSearch(event.target.value)}
                sx={{ minWidth: { xs: "100%", sm: 240 } }}
              />
              <Button variant="outlined" onClick={loadData} sx={greenOutlinedButtonSx}>
                Refresh
              </Button>
              <Button
                variant="outlined"
                onClick={handleSyncAllMailAccounts}
                disabled={!mailAccounts.length || accountActionId === "sync-all"}
                sx={greenOutlinedButtonSx}
              >
                {accountActionId === "sync-all" ? "Syncing..." : "Sync All"}
              </Button>
              <Button
                  variant="contained"
                  onClick={handleStartMailOAuth}
                  disabled={connectingMail || Boolean(mailOAuthState)}
                  sx={greenContainedButtonSx}
                >
                  {connectingMail || mailOAuthState ? "Adding..." : "Add Gmail"}
                </Button>
            </Stack>
          </Stack>

          <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Account</TableCell>
                  <TableCell>Inbox</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Last Sync</TableCell>
                  <TableCell align="right" sx={{ minWidth: 340 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredMailAccounts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} align="center">
                      {mailAccounts.length === 0 ? "No accounts connected." : "No accounts found."}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredMailAccounts.map((account) => {
                    const labelValue = normalizeLabelIds(account.label_ids || ["INBOX"]);
                    const updateActionId = `${account.id}:update`;
                    const syncActionId = `${account.id}:sync`;
                    const deleteActionId = `${account.id}:delete`;

                    return (
                      <TableRow key={account.id || account.account_email}>
                        <TableCell sx={{ minWidth: 220 }}>
                          <Typography fontWeight={700}>{account.account_email || "-"}</Typography>
                        </TableCell>
                        <TableCell sx={{ minWidth: 260 }}>
                          <FormControl size="small" fullWidth>
                            <Select
                              multiple
                              value={labelValue}
                              renderValue={formatLabelSelection}
                              onChange={(event) =>
                                handleAutoSaveAccountLabels(account, event.target.value)
                              }
                              disabled={accountActionId === updateActionId}
                            >
                              {MAIL_LABEL_OPTIONS.map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                  <Checkbox
                                    checked={labelValue.includes(option.value)}
                                    sx={greenCheckboxSx}
                                  />
                                  <ListItemText primary={option.label} />
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                        </TableCell>
                        <TableCell>
                          <Stack spacing={0.75} alignItems="flex-start">
                            {account.last_sync_status ? (
                              <Chip
                                size="small"
                                label={account.last_sync_status}
                                color={statusChipColor(account.last_sync_status)}
                              />
                            ) : (
                              <Chip size="small" label="pending" color="warning" />
                            )}
                            {account.last_error_message ? (
                              <Typography variant="body2" color="error">
                                {account.last_error_message}
                              </Typography>
                            ) : null}
                          </Stack>
                        </TableCell>
                        <TableCell>{formatDateTime(account.last_synced_at)}</TableCell>
                        <TableCell align="right" sx={{ minWidth: 340 }}>
                          <Stack direction="row" spacing={1} justifyContent="flex-end" useFlexGap flexWrap="wrap">
                            <Tooltip title={accountActionId === syncActionId ? "Syncing" : "Sync"}>
                              <span>
                                <IconButton
                                  size="small"
                                  aria-label="Sync account"
                                  onClick={() => handleSyncMailAccount(account)}
                                  disabled={accountActionId === syncActionId}
                                  sx={greenIconButtonSx}
                                >
                                  <SyncRoundedIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                            <Tooltip title={accountActionId === deleteActionId ? "Removing" : "Remove"}>
                              <span>
                                <IconButton
                                  size="small"
                                  aria-label="Remove account"
                                  onClick={() => handleDeleteMailAccount(account)}
                                  disabled={accountActionId === deleteActionId}
                                  sx={redIconButtonSx}
                                >
                                  <DeleteOutlineRoundedIcon fontSize="small" />
                                </IconButton>
                              </span>
                            </Tooltip>
                          </Stack>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}

      <Dialog open={Boolean(selectedMessageId)} onClose={handleCloseMessage} fullWidth maxWidth="lg">
        <DialogTitle sx={{ pb: 1 }}>
          <Typography variant="h6" fontWeight={800}>
            {selectedMessageDetail?.subject || "Email content"}
          </Typography>
          <Stack direction="row" spacing={1} alignItems="center" useFlexGap flexWrap="wrap" sx={{ color: "text.secondary", mt: 0.5 }}>
            <Typography variant="body2">
              {selectedMessageDetail?.from_name || selectedMessageDetail?.from_email || "-"}
            </Typography>
            <EastRoundedIcon sx={{ fontSize: 16, opacity: 0.8 }} />
            <Typography variant="body2">
              {selectedMessageDetail?.to_email || selectedMessageDetail?.mailbox || "-"}
            </Typography>
            <Typography variant="body2">|</Typography>
            <Typography variant="body2">{formatDateTime(selectedMessageDetail?.received_at)}</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent dividers sx={{ p: 0 }}>
          {selectedMessageLoading ? (
            <Box sx={{ p: 3 }}>
              <Typography>Loading email content...</Typography>
            </Box>
          ) : selectedMessageError ? (
            <Box sx={{ p: 3 }}>
              <Alert severity="error">{selectedMessageError}</Alert>
            </Box>
          ) : (
            <Box sx={{ p: 3 }}>
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, overflow: "hidden" }}>
                {selectedMessageHtml ? (
                  <Box
                    component="iframe"
                    title={`email-preview-${selectedMessageDetail?.id || "message"}`}
                    srcDoc={selectedMessageHtmlDoc}
                    sandbox="allow-popups allow-popups-to-escape-sandbox"
                    sx={{ width: "100%", minHeight: 620, border: 0, bgcolor: "#ffffff" }}
                  />
                ) : (
                  <Typography component="pre" sx={{ m: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "inherit" }}>
                    {selectedMessageBody || "This email does not have a stored full body yet."}
                  </Typography>
                )}
              </Paper>

              {!selectedMessageBody && selectedMessageDetail?.snippet ? (
                <Alert severity="info" sx={{ mt: 2 }}>
                  This message was ingested before full-body capture was enabled. Only preview text is available.
                </Alert>
              ) : null}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseMessage}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MailMonitor;
