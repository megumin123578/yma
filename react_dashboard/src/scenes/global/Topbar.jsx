import {
  Avatar,
  Badge,
  Box,
  Button,
  IconButton,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
  useTheme,
} from "@mui/material";
import { useContext, useEffect, useRef, useState } from "react";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import NotificationsNoneOutlinedIcon from "@mui/icons-material/NotificationsNoneOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";

import { ColorModeContext } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";
import MailMessageDialog from "../../components/MailMessageDialog";
import { uploadCredentials } from "../../services/userService";
import api from "../../services/api";

const MAIL_NOTIFICATION_STORAGE_KEY = "mailMonitor.matchedSeenIds";
const MAIL_NOTIFICATION_POLL_MS = 30000;
const MAIL_NOTIFICATION_LIMIT = 50;
const MAIL_NOTIFICATION_INITIAL_VISIBLE = 5;

const buildNotificationStorageKey = (user) => {
  const identity = [user?.id, user?.username]
    .map((value) => String(value || "").trim())
    .find(Boolean);
  return identity ? `${MAIL_NOTIFICATION_STORAGE_KEY}:${identity}` : MAIL_NOTIFICATION_STORAGE_KEY;
};

const loadStoredIds = (key) => {
  try {
    const raw = localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.map((value) => String(value)).filter(Boolean) : [];
  } catch {
    return [];
  }
};

const persistStoredIds = (key, ids, limit = 500) => {
  try {
    localStorage.setItem(
      key,
      JSON.stringify(Array.from(new Set(ids.map((value) => String(value)))).slice(0, limit))
    );
  } catch {
    // Ignore localStorage failures to keep header responsive.
  }
};

const formatNotificationTime = (value) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const Topbar = ({ setIsSidebar, isSidebar, isMobile = false }) => {
  const theme = useTheme();
  const colorMode = useContext(ColorModeContext);
  const { user } = useContext(UserContext);

  const [openProfile, setOpenProfile] = useState(false);
  const [addingChannel, setAddingChannel] = useState(false);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState(null);
  const [notificationItems, setNotificationItems] = useState([]);
  const [visibleNotificationCount, setVisibleNotificationCount] = useState(
    MAIL_NOTIFICATION_INITIAL_VISIBLE
  );
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [selectedMessageDetail, setSelectedMessageDetail] = useState(null);
  const [selectedMessageLoading, setSelectedMessageLoading] = useState(false);
  const [selectedMessageError, setSelectedMessageError] = useState("");

  const hasInitializedNotificationsRef = useRef(false);
  const notificationStorageKey = buildNotificationStorageKey(user);

  const avatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? `${process.env.REACT_APP_API_URL || ""}${user.avatar}`
      : null;
  const seenNotificationIds = new Set(loadStoredIds(notificationStorageKey));
  const unreadCount = notificationItems.filter(
    (item) => item?.id && !seenNotificationIds.has(String(item.id))
  ).length;
  const visibleNotificationItems = notificationItems.slice(0, visibleNotificationCount);
  const hasMoreNotifications = notificationItems.length > visibleNotificationCount;

  const shimmerSx = {
    position: "relative",
    overflow: "hidden",
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
    "&:hover:before": {
      transform: "translateX(260%)",
    },
  };

  const markNotificationIdsAsRead = (ids) => {
    const nextIds = (ids || []).map((value) => String(value)).filter(Boolean);
    if (nextIds.length === 0) return;
    const seenIds = loadStoredIds(notificationStorageKey);
    persistStoredIds(notificationStorageKey, [...seenIds, ...nextIds]);
    setNotificationItems((current) =>
      current.map((item) =>
        nextIds.includes(String(item?.id || ""))
          ? { ...item, __read: true }
          : item
      )
    );
  };

  const handleAddChannel = async () => {
    if (addingChannel) return;
    setAddingChannel(true);
    try {
      const data = await uploadCredentials();
      const nextUrl = data?.auth_url || "";
      if (nextUrl) {
        window.open(nextUrl, "_blank", "noopener");
      }
    } finally {
      setAddingChannel(false);
    }
  };

  const handleOpenNotifications = (event) => {
    setNotificationAnchorEl(event.currentTarget);
    setVisibleNotificationCount(MAIL_NOTIFICATION_INITIAL_VISIBLE);
  };

  const handleCloseNotifications = () => {
    setNotificationAnchorEl(null);
  };

  const handleShowPreviousNotifications = () => {
    setVisibleNotificationCount((current) =>
      Math.min(current + MAIL_NOTIFICATION_INITIAL_VISIBLE, notificationItems.length)
    );
  };

  const handleOpenNotificationItem = async (item) => {
    const messageId = item?.id;
    if (!messageId) return;
    markNotificationIdsAsRead([messageId]);
    handleCloseNotifications();
    setSelectedMessageId(messageId);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(true);
    try {
      const response = await api.get(`/api/mail/messages/${messageId}`);
      setSelectedMessageDetail(response.data || null);
    } catch (error) {
      setSelectedMessageError(
        error?.response?.data?.detail || error?.message || "Failed to load email content."
      );
    } finally {
      setSelectedMessageLoading(false);
    }
  };

  const handleCloseSelectedMessage = () => {
    setSelectedMessageId(null);
    setSelectedMessageDetail(null);
    setSelectedMessageError("");
    setSelectedMessageLoading(false);
  };

  useEffect(() => {
    hasInitializedNotificationsRef.current = false;
    setNotificationItems([]);
    setVisibleNotificationCount(MAIL_NOTIFICATION_INITIAL_VISIBLE);
    setNotificationAnchorEl(null);
  }, [notificationStorageKey]);

  useEffect(() => {
    if (!user) return undefined;

    const pollMatchedNotifications = async () => {
      try {
        const response = await api.get("/api/mail/messages", {
          params: {
            status: "matched",
            limit: MAIL_NOTIFICATION_LIMIT,
          },
        });
        const items = Array.isArray(response?.data?.items) ? response.data.items : [];
        const latestIds = items
          .map((item) => String(item?.id || ""))
          .filter(Boolean);

        if (!hasInitializedNotificationsRef.current) {
          const initialSeenIds = loadStoredIds(notificationStorageKey);
          if (initialSeenIds.length === 0) {
            persistStoredIds(notificationStorageKey, latestIds);
          }
          hasInitializedNotificationsRef.current = true;
        }

        const seenIds = new Set(loadStoredIds(notificationStorageKey));
        setNotificationItems(
          items.map((item) => ({
            ...item,
            __read: item?.id ? seenIds.has(String(item.id)) : true,
          }))
        );
      } catch {
        // Keep current notification state on transient failures.
      }
    };

    pollMatchedNotifications();
    const timer = window.setInterval(pollMatchedNotifications, MAIL_NOTIFICATION_POLL_MS);
    return () => window.clearInterval(timer);
  }, [notificationStorageKey, user]);

  return (
    <>
      <Box
        display="flex"
        justifyContent="flex-end"
        px={2}
        py={1.25}
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 1100,
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(17, 24, 39, 0.82)"
              : "rgba(255, 255, 255, 0.82)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
          <Box display="flex" alignItems="center">
            <IconButton
              size="medium"
              onClick={() => setIsSidebar?.((prev) => !prev)}
              sx={{ mr: 1 }}
            >
              <MenuOutlinedIcon fontSize="medium" />
            </IconButton>
          </Box>

          <Box display="flex" alignItems="center">
            <Button
              variant="contained"
              size="small"
              onClick={handleAddChannel}
              disabled={addingChannel}
              sx={{
                ...shimmerSx,
                mx: 1,
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
                "&:hover": {
                  bgcolor: theme.palette.mode === "dark" ? "#247468" : theme.palette.primary.dark,
                  transform: "translateY(-1px)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 26px rgba(43,138,123,0.34)"
                      : "0 14px 26px rgba(25,118,210,0.28)",
                },
              }}
            >
              Add Channel
            </Button>

            <IconButton size="medium" aria-label="Notifications" onClick={handleOpenNotifications}>
              <Badge
                color="error"
                badgeContent={unreadCount}
                max={99}
                overlap="circular"
                invisible={unreadCount <= 0}
              >
                <NotificationsNoneOutlinedIcon fontSize="medium" />
              </Badge>
            </IconButton>

            <IconButton
              size="medium"
              onClick={colorMode.toggleColorMode}
              aria-label="Toggle theme"
            >
              {theme.palette.mode === "dark" ? (
                <DarkModeOutlinedIcon fontSize="medium" />
              ) : (
                <LightModeOutlinedIcon fontSize="medium" />
              )}
            </IconButton>

            <IconButton size="medium" onClick={() => setOpenProfile(true)}>
              {avatarSrc ? (
                <Avatar src={avatarSrc} sx={{ width: 32, height: 32 }} />
              ) : (
                <PersonOutlinedIcon fontSize="medium" />
              )}
            </IconButton>
          </Box>
        </Box>
      </Box>

      <Menu
        anchorEl={notificationAnchorEl}
        open={Boolean(notificationAnchorEl)}
        onClose={handleCloseNotifications}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{
          sx: {
            mt: 1,
            width: 360,
            maxWidth: "calc(100vw - 24px)",
            borderRadius: 3,
            border: "1px solid",
            borderColor:
              theme.palette.mode === "dark"
                ? "rgba(148,163,184,0.18)"
                : "rgba(15,23,42,0.08)",
            bgcolor:
              theme.palette.mode === "dark"
                ? "rgba(15,23,42,0.96)"
                : "rgba(255,255,255,0.98)",
            boxShadow:
              theme.palette.mode === "dark"
                ? "0 18px 40px rgba(2,6,23,0.46)"
                : "0 18px 36px rgba(148,163,184,0.22)",
          },
        }}
      >
        {notificationItems.length === 0 ? (
          <Box px={2} py={2.5}>
            <Typography variant="body2" color="text.secondary">
              Matched emails will appear here.
            </Typography>
          </Box>
        ) : (
          visibleNotificationItems.map((item) => (
            <MenuItem
              key={item.id}
              onClick={() => handleOpenNotificationItem(item)}
              sx={{
                alignItems: "flex-start",
                py: 1.25,
                whiteSpace: "normal",
                opacity: item.__read ? 0.56 : 1,
                filter: item.__read ? "blur(0.6px)" : "none",
                bgcolor:
                  item.__read
                    ? "transparent"
                    : theme.palette.mode === "dark"
                      ? "rgba(56,189,248,0.10)"
                      : "rgba(59,130,246,0.08)",
                "&:hover": {
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? item.__read
                        ? "rgba(148,163,184,0.08)"
                        : "rgba(56,189,248,0.16)"
                      : item.__read
                        ? "rgba(148,163,184,0.08)"
                        : "rgba(59,130,246,0.14)",
                },
              }}
            >
              <Box
                sx={{
                  width: 10,
                  height: 10,
                  borderRadius: "50%",
                  bgcolor:
                    item.__read
                      ? "transparent"
                      : theme.palette.mode === "dark"
                        ? "#67e8f9"
                        : "#16a34a",
                  flexShrink: 0,
                  mt: 0.9,
                  mr: 1.25,
                  border: item.__read ? "1px solid transparent" : "none",
                }}
              />
              <ListItemText
                primary={
                  <Typography variant="body2" fontWeight={700} noWrap>
                    {item.subject || "(no subject)"}
                  </Typography>
                }
                secondary={
                  <>
                    <Typography
                      component="span"
                      variant="body2"
                      color="text.primary"
                      sx={{ display: "block" }}
                      noWrap
                    >
                      {item.from_name || item.from_email || "Unknown sender"}
                    </Typography>
                    <Typography
                      component="span"
                      variant="caption"
                      color="text.secondary"
                      sx={{ display: "block", mt: 0.35 }}
                    >
                      {formatNotificationTime(item.received_at || item.last_seen_at)}
                    </Typography>
                  </>
                }
              />
            </MenuItem>
          ))
        )}

        {hasMoreNotifications ? (
          <Box px={1.5} py={1.25}>
            <Button
              fullWidth
              variant="outlined"
              onClick={handleShowPreviousNotifications}
              sx={{
                textTransform: "none",
                fontWeight: 700,
                borderRadius: 999,
                borderColor:
                  theme.palette.mode === "dark"
                    ? "rgba(103,232,249,0.42)"
                    : "rgba(37,99,235,0.24)",
                color: theme.palette.mode === "dark" ? "#67e8f9" : "#1d4ed8",
                bgcolor:
                  theme.palette.mode === "dark"
                    ? "rgba(8,47,73,0.34)"
                    : "rgba(239,246,255,0.95)",
                "&:hover": {
                  borderColor:
                    theme.palette.mode === "dark"
                      ? "rgba(103,232,249,0.62)"
                      : "rgba(37,99,235,0.38)",
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? "rgba(14,116,144,0.26)"
                      : "rgba(219,234,254,0.98)",
                },
              }}
            >
              See previous notifications
            </Button>
          </Box>
        ) : null}
      </Menu>

      <MailMessageDialog
        open={Boolean(selectedMessageId)}
        onClose={handleCloseSelectedMessage}
        loading={selectedMessageLoading}
        error={selectedMessageError}
        message={selectedMessageDetail}
      />

      <ProfileDialog open={openProfile} onClose={() => setOpenProfile(false)} />
    </>
  );
};

export default Topbar;
