import { useCallback, useContext, useEffect, useMemo, useState } from "react";
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
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import EastRoundedIcon from "@mui/icons-material/EastRounded";
import { useSearchParams } from "react-router-dom";

import api from "../services/api";
import { UserContext } from "../context/UserContext";

const MAILS_PER_PAGE = 50;

const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
};

const formatNumber = (value) => Number(value || 0).toLocaleString();

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

const MailMonitor = () => {
  const { user, loading } = useContext(UserContext);
  const isAdmin = !!user?.is_admin;
  const [searchParams, setSearchParams] = useSearchParams();

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

  const overviewItems = useMemo(
    () => (Array.isArray(overview?.items) ? overview.items : []).filter(Boolean),
    [overview]
  );
  const messageItems = useMemo(
    () => (Array.isArray(messages?.items) ? messages.items : []).filter(Boolean),
    [messages]
  );
  const summary = overview?.summary || {};

  const accountOptions = useMemo(() => {
    return [
      ...new Set(
        overviewItems
          .map((item) => item?.account_email)
          .filter(Boolean)
      ),
    ];
  }, [overviewItems]);

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
      return;
    }

    setError("");
    try {
      const [overviewResp, messagesResp] = await Promise.all([
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
      ]);

      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
    } catch (err) {
      if (err?.response?.status === 403) {
        setMailAccessDenied(true);
        setOverview({ summary: {}, items: [] });
        setMessages({ items: [], total: 0 });
        setError("Admin access required.");
        return;
      }
      setError(err?.response?.data?.detail || err?.message || "Failed to load email manager data.");
    }
  }, [filters.accountEmail, filters.mailbox, filters.search, filters.status, isAdmin, loading, mailAccessDenied, mailPage]);

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
    setMailAccessDenied(false);
  }, [user?.id, user?.username]);

  useEffect(() => {
    const tabParam = searchParams.get("tab");
    if (!tabParam) return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("tab");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const messageIdParam = searchParams.get("messageId");
    const normalizedMessageId = Number(messageIdParam);
    if (!messageIdParam || Number.isNaN(normalizedMessageId) || normalizedMessageId <= 0) return;
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

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} mb={2}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Messages</Typography>
          <Typography variant="h5" fontWeight={800}>{formatNumber(summary.total_messages)}</Typography>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, flex: 1 }}>
          <Typography variant="body2" color="text.secondary">Accounts</Typography>
          <Typography variant="h5" fontWeight={800}>{formatNumber(summary.account_count)}</Typography>
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
