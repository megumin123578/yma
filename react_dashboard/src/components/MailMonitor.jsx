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
  InputLabel,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Switch,
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
} from "@mui/material";
import EastRoundedIcon from "@mui/icons-material/EastRounded";
import { useSearchParams } from "react-router-dom";

import api from "../services/api";
import { subscribeSSE } from "../services/sse";
import { startMailOAuth } from "../services/userService";
import { UserContext, useHasPermission } from "../context/UserContext";
import { formatDateTimeInSaigon, formatTimeInSaigon } from "../utils/dateTime";

const MAILS_PER_PAGE = 50;
const MAIL_MONITOR_STORAGE_KEY = "mailMonitor.uiState";
const DEFAULT_MAIL_FILTERS = {
  accountEmail: "",
  mailbox: "",
  status: "matched",
  search: "",
};
const MAIL_LABEL_OPTIONS = [
  { value: "INBOX", label: "Inbox" },
  { value: "CATEGORY_UPDATES", label: "Updates" },
  { value: "CATEGORY_PROMOTIONS", label: "Promotions" },
  { value: "CATEGORY_SOCIAL", label: "Social" },
  { value: "CATEGORY_FORUMS", label: "Forums" },
];

const formatDateTime = (value) => formatDateTimeInSaigon(value, String(value || "-"));

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

const normalizeAccountEmail = (value) => String(value || "").trim().toLowerCase();

const getMailAccountKey = (account) => String(account?.id ?? account?.account_email ?? "");

const hasMailStateInSearchParams = (searchParams) =>
  ["account", "mailbox", "status", "search", "page", "accountSearch"].some((key) =>
    searchParams.has(key)
  );

const readMailMonitorStateFromStorage = () => {
  if (typeof window === "undefined") return null;
  try {
    const rawValue = window.localStorage.getItem(MAIL_MONITOR_STORAGE_KEY);
    if (!rawValue) return null;
    const parsed = JSON.parse(rawValue);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
};

const readMailFiltersFromSearchParams = (searchParams) => ({
  accountEmail: searchParams.get("account") || DEFAULT_MAIL_FILTERS.accountEmail,
  mailbox: searchParams.get("mailbox") || DEFAULT_MAIL_FILTERS.mailbox,
  status: searchParams.get("status") ?? DEFAULT_MAIL_FILTERS.status,
  search: searchParams.get("search") || DEFAULT_MAIL_FILTERS.search,
});

const normalizeMailFilters = (value) => ({
  accountEmail: String(value?.accountEmail || ""),
  mailbox: String(value?.mailbox || ""),
  status: String(value?.status ?? DEFAULT_MAIL_FILTERS.status),
  search: String(value?.search || ""),
});

const areMailFiltersEqual = (left, right) =>
  left.accountEmail === right.accountEmail &&
  left.mailbox === right.mailbox &&
  left.status === right.status &&
  left.search === right.search;

const readMailPageFromSearchParams = (searchParams) => {
  const rawValue = searchParams.get("page");
  const page = Number(rawValue);
  return Number.isInteger(page) && page >= 0 ? page : 0;
};

const readAccountSearchFromSearchParams = (searchParams) => searchParams.get("accountSearch") || "";

const readInitialMailFilters = (searchParams) => {
  if (hasMailStateInSearchParams(searchParams)) {
    return readMailFiltersFromSearchParams(searchParams);
  }
  return normalizeMailFilters(readMailMonitorStateFromStorage()?.filters);
};

const readInitialMailPage = (searchParams) => {
  if (hasMailStateInSearchParams(searchParams)) {
    return readMailPageFromSearchParams(searchParams);
  }
  const page = Number(readMailMonitorStateFromStorage()?.mailPage);
  return Number.isInteger(page) && page >= 0 ? page : 0;
};

const readInitialAccountSearch = (searchParams) => {
  if (hasMailStateInSearchParams(searchParams)) {
    return readAccountSearchFromSearchParams(searchParams);
  }
  return String(readMailMonitorStateFromStorage()?.accountSearch || "");
};

const statusChipColor = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "error") return "error";
  if (normalized === "ok" || normalized === "completed") return "success";
  if (normalized === "matched") return "info";
  if (normalized === "pending") return "warning";
  return "default";
};

const statusDotColor = (status) => {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "error") return "error.main";
  if (normalized === "ok" || normalized === "completed") return "success.main";
  if (normalized === "matched") return "info.main";
  if (normalized === "pending") return "warning.main";
  return "text.disabled";
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

const topbarLikeButtonSx = (theme) => ({
  position: "relative",
  overflow: "hidden",
  borderRadius: 999,
  textTransform: "none",
  fontWeight: 700,
  minWidth: 0,
  px: 1.25,
  py: 0.45,
  lineHeight: 1.2,
  minHeight: 30,
  bgcolor: theme.palette.mode === "dark" ? "#2b8a7b" : theme.palette.primary.main,
  color: "#fff",
  boxShadow:
    theme.palette.mode === "dark"
      ? "0 10px 22px rgba(43,138,123,0.28)"
      : "0 10px 22px rgba(25,118,210,0.22)",
  transition: "all 180ms ease",
  "&:before": {
    content: '""',
    position: "absolute",
    top: "-50%",
    left: "-120%",
    width: "80%",
    height: "200%",
    background:
      "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.45) 45%, transparent 90%)",
    transform: "translateX(0)",
    transition: "transform 0.7s ease",
    opacity: 0.8,
    pointerEvents: "none",
  },
  "&:hover": {
    bgcolor: theme.palette.mode === "dark" ? "#247468" : theme.palette.primary.dark,
    transform: "translateY(-1px)",
    boxShadow:
      theme.palette.mode === "dark"
        ? "0 14px 26px rgba(43,138,123,0.34)"
        : "0 14px 26px rgba(25,118,210,0.28)",
  },
  "&:hover:before": {
    transform: "translateX(260%)",
  },
  "&.Mui-disabled": {
    bgcolor: "rgba(148, 163, 184, 0.24)",
    color: "text.disabled",
    boxShadow: "none",
  },
});

const redOutlinedButtonSx = {
  backgroundColor: "rgba(219, 79, 74, 0.08)",
  "&:hover": {
    backgroundColor: "rgba(219, 79, 74, 0.16)",
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(() =>
    searchParams.get("tab") === "accounts" ? "accounts" : "messages"
  );

  const [overview, setOverview] = useState({ summary: {}, items: [] });
  const [messages, setMessages] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState(() => readInitialMailFilters(searchParams));
  const [mailPage, setMailPage] = useState(() => readInitialMailPage(searchParams));
  const [error, setError] = useState("");
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [selectedMessageDetail, setSelectedMessageDetail] = useState(null);
  const [selectedMessageLoading, setSelectedMessageLoading] = useState(false);
  const [selectedMessageError, setSelectedMessageError] = useState("");
  const [mailAccounts, setMailAccounts] = useState([]);
  const [mailOAuthState, setMailOAuthState] = useState("");
  const [mailOAuthStatus, setMailOAuthStatus] = useState({ type: "", message: "" });
  const [connectingMail, setConnectingMail] = useState(false);
  const [accountSearch, setAccountSearch] = useState(() => readInitialAccountSearch(searchParams));
  const [accountActionStatus, setAccountActionStatus] = useState({ type: "", message: "" });
  const [accountActionId, setAccountActionId] = useState("");
  const [channelNameDrafts, setChannelNameDrafts] = useState({});

  const overviewItems = useMemo(
    () => (Array.isArray(overview?.items) ? overview.items : []).filter(Boolean),
    [overview]
  );
  const messageItems = useMemo(
    () => (Array.isArray(messages?.items) ? messages.items : []).filter(Boolean),
    [messages]
  );
  const isMailAdmin = useHasPermission("manage_mail");
  const summary = overview?.summary || {};
  const connectedAccountCount = mailAccounts.length || Number(summary.account_count || 0);
  const accountMailTotals = useMemo(() => {
    return overviewItems.reduce((totals, item) => {
      const accountEmail = normalizeAccountEmail(item?.account_email);
      if (!accountEmail) return totals;
      totals[accountEmail] = (totals[accountEmail] || 0) + Number(item?.total_messages || 0);
      return totals;
    }, {});
  }, [overviewItems]);
  const filteredMailAccounts = useMemo(() => {
    const searchText = accountSearch.trim().toLowerCase();
    if (!searchText) return mailAccounts;
    return mailAccounts.filter((account) =>
      String(account?.account_email || "").toLowerCase().includes(searchText) ||
      String(account?.channel_name || "").toLowerCase().includes(searchText)
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
    if (loading) {
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
          },
        }),
        api.get("/api/mail/accounts"),
      ]);

      setOverview(overviewResp.data || { summary: {}, items: [] });
      setMessages(messagesResp.data || { items: [], total: 0 });
      setMailAccounts(Array.isArray(accountsResp.data?.items) ? accountsResp.data.items : []);
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || "Failed to load email manager data.");
    }
  }, [filters.accountEmail, filters.mailbox, filters.search, filters.status, loading, mailPage]);

  const updateFilters = useCallback((updater) => {
    setMailPage(0);
    setFilters((current) => {
      if (typeof updater === "function") {
        return updater(current);
      }
      return { ...current, ...updater };
    });
  }, []);

  const handleStartMailOAuth = useCallback(async () => {
    if (connectingMail) return;
    setConnectingMail(true);
    setMailOAuthStatus({ type: "", message: "" });
    try {
      const response = await startMailOAuth();
      const nextUrl = response?.auth_url || "";
      const nextState = response?.state || "";
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

  const handleTestMailLog = useCallback(async () => {
    setAccountActionId("test-log");
    setAccountActionStatus({ type: "", message: "" });
    try {
      const response = await api.post("/api/mail/test-log");
      setAccountActionStatus({
        type: "success",
        message: response?.data?.message || "Backend mail test log emitted.",
      });
    } catch (err) {
      setAccountActionStatus({
        type: "error",
        message: err?.response?.data?.detail || err?.message || "Failed to emit backend mail test log.",
      });
    } finally {
      setAccountActionId("");
    }
  }, []);

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
    if (loading) return undefined;
    loadData();
    return undefined;
  }, [loadData, loading]);

  useEffect(() => {
    if (loading) return undefined;

    const params = new URLSearchParams();
    if (filters.accountEmail) params.set("account_email", filters.accountEmail);
    if (filters.mailbox) params.set("mailbox", filters.mailbox);
    if (filters.status) params.set("status", filters.status);
    if (filters.search) params.set("search", filters.search);
    params.set("limit", String(MAILS_PER_PAGE));
    params.set("offset", String(mailPage * MAILS_PER_PAGE));

    const unsubscribe = subscribeSSE(`/api/mail/messages/stream?${params.toString()}`, {
      onMessage: ({ event, data }) => {
        if (event === "error" || !data) return;
        setMessages(data);
      },
    });

    return () => {
      unsubscribe();
    };
  }, [
    loading,
    filters.accountEmail,
    filters.mailbox,
    filters.status,
    filters.search,
    mailPage,
  ]);

  useEffect(() => {
    if (!mailOAuthState || loading) return undefined;

    let resolved = false;

    const unsubscribe = subscribeSSE(
      `/api/mail/accounts/oauth/state/${encodeURIComponent(mailOAuthState)}/stream`,
      {
        onMessage: async ({ event, data }) => {
          if (resolved || !data) return;
          if (event === "error") {
            resolved = true;
            setMailOAuthState("");
            setMailOAuthStatus({
              type: "error",
              message: data?.error || "Failed to check Gmail authorization.",
            });
            unsubscribe();
            return;
          }
          if (data.ready || data.status === "completed") {
            resolved = true;
            setMailOAuthState("");
            setMailOAuthStatus({
              type: "success",
              message: data.account_email
                ? `Gmail connected: ${data.account_email}`
                : "Gmail connected.",
            });
            await loadData();
            unsubscribe();
            return;
          }
          if (data.status === "failed" || data.status === "expired") {
            resolved = true;
            setMailOAuthState("");
            setMailOAuthStatus({
              type: "error",
              message: data.error_message || "Gmail authorization did not complete.",
            });
            unsubscribe();
          }
        },
        onError: () => {
          if (resolved) return;
          resolved = true;
          setMailOAuthState("");
          setMailOAuthStatus({
            type: "error",
            message: "Failed to check Gmail authorization.",
          });
        },
      }
    );

    return () => {
      unsubscribe();
    };
  }, [loadData, loading, mailOAuthState]);

  useEffect(() => {
    setMailOAuthState("");
    setMailOAuthStatus({ type: "", message: "" });
    setAccountActionStatus({ type: "", message: "" });
    setAccountActionId("");
  }, [user?.id, user?.username]);

  useEffect(() => {
    if (!hasMailStateInSearchParams(searchParams)) return;

    const nextFilters = readMailFiltersFromSearchParams(searchParams);
    setFilters((current) => (areMailFiltersEqual(current, nextFilters) ? current : nextFilters));

    const nextMailPage = readMailPageFromSearchParams(searchParams);
    setMailPage((current) => (current === nextMailPage ? current : nextMailPage));

    const nextAccountSearch = readAccountSearchFromSearchParams(searchParams);
    setAccountSearch((current) => (current === nextAccountSearch ? current : nextAccountSearch));
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      MAIL_MONITOR_STORAGE_KEY,
      JSON.stringify({
        filters,
        mailPage,
        accountSearch,
      })
    );
  }, [accountSearch, filters, mailPage]);

  useEffect(() => {
    setSearchParams((currentParams) => {
      const nextParams = new URLSearchParams(currentParams);

      if (filters.accountEmail) nextParams.set("account", filters.accountEmail);
      else nextParams.delete("account");

      if (filters.mailbox) nextParams.set("mailbox", filters.mailbox);
      else nextParams.delete("mailbox");

      if (filters.status && filters.status !== DEFAULT_MAIL_FILTERS.status) {
        nextParams.set("status", filters.status);
      } else {
        nextParams.delete("status");
      }

      const searchValue = filters.search.trim();
      if (searchValue) nextParams.set("search", searchValue);
      else nextParams.delete("search");

      if (mailPage > 0) nextParams.set("page", String(mailPage));
      else nextParams.delete("page");

      const accountSearchValue = accountSearch.trim();
      if (accountSearchValue) nextParams.set("accountSearch", accountSearchValue);
      else nextParams.delete("accountSearch");

      return nextParams;
    }, { replace: true });
  }, [
    accountSearch,
    filters.accountEmail,
    filters.mailbox,
    filters.search,
    filters.status,
    mailPage,
    setSearchParams,
  ]);

  useEffect(() => {
    setChannelNameDrafts((current) => {
      const next = {};
      mailAccounts.forEach((account) => {
        const key = getMailAccountKey(account);
        if (!key) return;
        if (Object.prototype.hasOwnProperty.call(current, key)) {
          next[key] = current[key];
          return;
        }
        next[key] = String(account?.channel_name || "");
      });
      return next;
    });
  }, [mailAccounts]);

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

  const handleChannelNameDraftChange = (account, value) => {
    const key = getMailAccountKey(account);
    if (!key) return;
    setChannelNameDrafts((current) => ({
      ...current,
      [key]: value,
    }));
  };

  const handleCommitChannelName = async (account) => {
    const key = getMailAccountKey(account);
    if (!key) return;
    const nextValue = String(channelNameDrafts[key] ?? account?.channel_name ?? "").trim();
    const currentValue = String(account?.channel_name || "").trim();
    if (nextValue === currentValue) return;
    await handleUpdateMailAccount(account, { channel_name: nextValue || null });
    setChannelNameDrafts((current) => ({
      ...current,
      [key]: nextValue,
    }));
  };

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
          sx={(theme) => ({
            "& .MuiTab-root": {
              fontWeight: 700,
              color: theme.palette.mode === "light" ? theme.palette.primary.main : "#60a5fa",
              opacity: 1,
            },
            "& .MuiTab-root.Mui-selected": {
              color: theme.palette.mode === "light" ? theme.palette.primary.main : "#60a5fa",
            },
            "& .MuiTabs-indicator": {
              backgroundColor:
                theme.palette.mode === "light" ? theme.palette.primary.main : "#ffffff",
            },
          })}
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
                    updateFilters((current) => ({
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
                  onChange={(event) => updateFilters((current) => ({ ...current, mailbox: event.target.value }))}
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
                  onChange={(event) => updateFilters((current) => ({ ...current, status: event.target.value }))}
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
                onChange={(event) => updateFilters((current) => ({ ...current, search: event.target.value }))}
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
              {isMailAdmin ? (
                <Button
                  variant="outlined"
                  onClick={handleTestMailLog}
                  disabled={accountActionId === "test-log"}
                  sx={greenOutlinedButtonSx}
                >
                  {accountActionId === "test-log" ? "Testing..." : "Test Email"}
                </Button>
              ) : null}
              <Button
                variant="contained"
                onClick={handleStartMailOAuth}
                disabled={connectingMail || Boolean(mailOAuthState)}
                sx={topbarLikeButtonSx}
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
                  <TableCell>Channel Name</TableCell>
                  <TableCell align="right">Total Mails</TableCell>
                  <TableCell>Inbox</TableCell>
                  <TableCell>Last Sync</TableCell>
                  <TableCell>Auto Sync</TableCell>
                  <TableCell align="right" sx={{ minWidth: 340 }}>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredMailAccounts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      {mailAccounts.length === 0 ? "No accounts connected." : "No accounts found."}
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredMailAccounts.map((account) => {
                    const accountKey = getMailAccountKey(account);
                    const draftChannelName = channelNameDrafts[accountKey] ?? String(account?.channel_name || "");
                    const totalMailCount = Number(
                      accountMailTotals[normalizeAccountEmail(account?.account_email)] || 0
                    );
                    const labelValue = normalizeLabelIds(account.label_ids || ["INBOX"]);
                    const updateActionId = `${account.id}:update`;
                    const syncActionId = `${account.id}:sync`;
                    const deleteActionId = `${account.id}:delete`;

                    return (
                      <TableRow key={account.id || account.account_email}>
                        <TableCell sx={{ minWidth: 260 }}>
                          <Stack spacing={0.5}>
                            <Stack direction="row" spacing={1} alignItems="center">
                              <Box
                                component="span"
                                title={account.last_sync_status || "pending"}
                                sx={{
                                  width: 10,
                                  height: 10,
                                  borderRadius: "50%",
                                  flexShrink: 0,
                                  bgcolor: statusDotColor(account.last_sync_status || "pending"),
                                }}
                              />
                              <Typography fontWeight={700}>{account.account_email || "-"}</Typography>
                            </Stack>
                            {account.last_error_message ? (
                              <Typography variant="body2" color="error">
                                {account.last_error_message}
                              </Typography>
                            ) : null}
                          </Stack>
                        </TableCell>
                        <TableCell sx={{ minWidth: 220 }}>
                          <TextField
                            size="small"
                            fullWidth
                            placeholder="Channel name"
                            value={draftChannelName}
                            onChange={(event) => handleChannelNameDraftChange(account, event.target.value)}
                            onBlur={() => handleCommitChannelName(account)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                event.currentTarget.blur();
                              }
                            }}
                            disabled={accountActionId === updateActionId}
                          />
                        </TableCell>
                        <TableCell align="right" sx={{ minWidth: 120 }}>
                          <Typography fontWeight={700}>{formatNumber(totalMailCount)}</Typography>
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
                        <TableCell>{formatTimeInSaigon(account.last_synced_at)}</TableCell>
                        <TableCell sx={{ minWidth: 150 }}>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Switch
                              size="small"
                              checked={Boolean(account.enabled)}
                              onChange={(event) =>
                                handleUpdateMailAccount(account, { enabled: event.target.checked })
                              }
                              disabled={accountActionId === updateActionId}
                              color="secondary"
                            />
                            <Typography variant="body2" fontWeight={700}>
                              {account.enabled ? "On" : "Off"}
                            </Typography>
                          </Stack>
                        </TableCell>
                        <TableCell align="right" sx={{ minWidth: 340 }}>
                          <Stack direction="row" spacing={1} justifyContent="flex-end" useFlexGap flexWrap="wrap">
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => handleSyncMailAccount(account)}
                              disabled={accountActionId === syncActionId}
                              sx={greenOutlinedButtonSx}
                            >
                              {accountActionId === syncActionId ? "Syncing..." : "Sync"}
                            </Button>
                            <Button
                              size="small"
                              color="error"
                              variant="outlined"
                              onClick={() => handleDeleteMailAccount(account)}
                              disabled={accountActionId === deleteActionId}
                              sx={redOutlinedButtonSx}
                            >
                              {accountActionId === deleteActionId ? "Removing..." : "Remove"}
                            </Button>
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
