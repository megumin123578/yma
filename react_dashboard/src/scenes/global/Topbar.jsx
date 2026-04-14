import {
  Avatar,
  Badge,
  Box,
  Button,
  IconButton,
  ListItemIcon,
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
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import SmartDisplayRoundedIcon from "@mui/icons-material/SmartDisplayRounded";
import AlternateEmailRoundedIcon from "@mui/icons-material/AlternateEmailRounded";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import { alpha } from "@mui/material/styles";

import { useNavigate } from "react-router-dom";
import { ColorModeContext, tokens } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";
import MailMessageDialog from "../../components/MailMessageDialog";
import { startMailOAuth, uploadCredentials } from "../../services/userService";
import api from "../../services/api";
import { formatShortDateTimeInSaigon } from "../../utils/dateTime";

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

const formatNotificationTime = (value) => formatShortDateTimeInSaigon(value, "");

const Topbar = ({ onToggleSidebar, desktopSidebarMode = "expanded", isMobile = false }) => {
  const theme = useTheme();
  const navigate = useNavigate();
  const colorMode = useContext(ColorModeContext);
  const { user, loading } = useContext(UserContext);
  const isMailAdmin = !!user?.is_admin;

  const [openProfile, setOpenProfile] = useState(false);
  const [addingChannel, setAddingChannel] = useState(false);
  const [addingMail, setAddingMail] = useState(false);
  const [addMenuAnchorEl, setAddMenuAnchorEl] = useState(null);
  const [notificationAnchorEl, setNotificationAnchorEl] = useState(null);
  const [notificationItems, setNotificationItems] = useState([]);
  const [visibleNotificationCount, setVisibleNotificationCount] = useState(
    MAIL_NOTIFICATION_INITIAL_VISIBLE
  );
  const [selectedMessageId, setSelectedMessageId] = useState(null);
  const [selectedMessageDetail, setSelectedMessageDetail] = useState(null);
  const [selectedMessageLoading, setSelectedMessageLoading] = useState(false);
  const [selectedMessageError, setSelectedMessageError] = useState("");
  const [mailAccessDenied, setMailAccessDenied] = useState(false);

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
  const addMenuOpen = Boolean(addMenuAnchorEl);
  const isAddingAny = addingChannel || addingMail;
  const addButtonLabel = isAddingAny ? "Adding..." : "+ Add";
  const nextThemeLabel =
    theme.palette.mode === "dark" ? "Switch to light mode" : "Switch to dark mode";
  const colorTokens = tokens(theme.palette.mode);
  const addButtonBg =
    theme.palette.mode === "dark" ? colorTokens.greenAccent[700] : theme.palette.primary.main;
  const addButtonHoverBg =
    theme.palette.mode === "dark" ? colorTokens.greenAccent[600] : theme.palette.primary.dark;
  const addButtonShadowColor =
    theme.palette.mode === "dark" ? colorTokens.greenAccent[500] : theme.palette.primary.main;
  const menuPaperBorder = alpha(theme.palette.divider, theme.palette.mode === "dark" ? 0.3 : 0.7);
  const menuPaperBg = alpha(
    theme.palette.background.paper,
    theme.palette.mode === "dark" ? 0.94 : 0.98
  );
  const menuPaperShadow =
    theme.palette.mode === "dark"
      ? `0 22px 44px ${alpha(theme.palette.common.black, 0.46)}`
      : `0 22px 44px ${alpha(colorTokens.primary[200], 0.18)}`;
  const notificationAccent =
    theme.palette.mode === "dark" ? theme.palette.info.light : theme.palette.info.dark;
  const unreadDotColor =
    theme.palette.mode === "dark" ? theme.palette.info.light : theme.palette.success.main;
  const addChannelAccent = theme.palette.error.main;
  const addGmailAccent = colorTokens.redAccent[400];
  const sidebarToggleLabel = isMobile
    ? "Toggle sidebar"
    : desktopSidebarMode === "expanded"
      ? "Collapse sidebar to icons"
      : desktopSidebarMode === "compact"
        ? "Hide sidebar"
        : "Show full sidebar";
  const addMenuPaperSx = {
    mt: 1,
    minWidth: 284,
    borderRadius: 3,
    overflow: "hidden",
    border: "1px solid",
    borderColor: menuPaperBorder,
    bgcolor: menuPaperBg,
    backdropFilter: "blur(14px)",
    WebkitBackdropFilter: "blur(14px)",
    boxShadow: menuPaperShadow,
  };
  const buildAddMenuItemSx = (accentColor) => ({
    mx: 1,
    my: 0.5,
    px: 1.2,
    py: 1,
    borderRadius: 2,
    alignItems: "flex-start",
    gap: 1.25,
    transition: "all 160ms ease",
    "&:hover": {
      backgroundColor: alpha(accentColor, theme.palette.mode === "dark" ? 0.18 : 0.1),
      transform: "translateY(-1px)",
    },
    "&.Mui-disabled": {
      opacity: 0.7,
    },
  });
  const buildAddMenuIconSx = (accentColor) => ({
    minWidth: 0,
    mt: 0.2,
    color: accentColor,
    p: 0.9,
    borderRadius: 1.6,
    backgroundColor: alpha(accentColor, theme.palette.mode === "dark" ? 0.18 : 0.12),
    boxShadow: `inset 0 0 0 1px ${alpha(accentColor, theme.palette.mode === "dark" ? 0.24 : 0.16)}`,
  });

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

  const handleAddGmail = async () => {
    if (addingMail) return;
    setAddingMail(true);
    try {
      const data = await startMailOAuth();
      const nextUrl = data?.auth_url || "";
      if (nextUrl) {
        window.open(nextUrl, "_blank", "noopener");
      }
    } finally {
      setAddingMail(false);
    }
  };

  const handleOpenAddMenu = (event) => {
    if (isAddingAny) return;
    setAddMenuAnchorEl(event.currentTarget);
  };

  const handleCloseAddMenu = () => {
    setAddMenuAnchorEl(null);
  };

  const handleSelectAddAction = async (type) => {
    handleCloseAddMenu();
    if (type === "gmail") {
      await handleAddGmail();
      return;
    }
    await handleAddChannel();
  };

  const handleOpenNotifications = (event) => {
    if (!isMailAdmin) return;
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

  const handleMarkNotificationAsRead = (event, messageId) => {
    event.preventDefault();
    event.stopPropagation();
    if (!messageId) return;
    markNotificationIdsAsRead([messageId]);
  };

  const handleMarkAllNotificationsAsRead = () => {
    const ids = notificationItems
      .map((item) => String(item?.id || "").trim())
      .filter(Boolean);
    markNotificationIdsAsRead(ids);
  };

  const handleOpenNotificationItem = async (item) => {
    if (!isMailAdmin) return;
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
    setMailAccessDenied(false);
  }, [notificationStorageKey]);

  useEffect(() => {
    if (loading || !user || !isMailAdmin || mailAccessDenied) {
      setNotificationItems([]);
      setNotificationAnchorEl(null);
      return undefined;
    }

    let isActive = true;
    let timerId = null;

    const pollMatchedNotifications = async () => {
      try {
        const response = await api.get("/api/mail/messages", {
          params: {
            status: "matched",
            limit: MAIL_NOTIFICATION_LIMIT,
          },
        });
        if (!isActive) return;
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
      } catch (error) {
        if (!isActive) return;
        if (error?.response?.status === 403) {
          setMailAccessDenied(true);
          setNotificationItems([]);
          setNotificationAnchorEl(null);
        }
      }
    };

    const stopPolling = () => {
      if (timerId !== null) {
        clearInterval(timerId);
        timerId = null;
      }
    };

    const startPolling = () => {
      if (document.visibilityState !== "visible" || timerId !== null) return;
      pollMatchedNotifications();
      timerId = setInterval(() => {
        if (document.visibilityState !== "visible") return;
        pollMatchedNotifications();
      }, MAIL_NOTIFICATION_POLL_MS);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        startPolling();
        return;
      }
      stopPolling();
    };

    handleVisibilityChange();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      isActive = false;
      stopPolling();
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isMailAdmin, loading, mailAccessDenied, notificationStorageKey, user]);

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
              onClick={onToggleSidebar}
              aria-label={sidebarToggleLabel}
              sx={{ mr: 1 }}
            >
              <MenuOutlinedIcon fontSize="medium" />
            </IconButton>
          </Box>

          <Box display="flex" alignItems="center" gap={1}>
            <Button
              variant="contained"
              size="small"
              onClick={handleOpenAddMenu}
              disabled={isAddingAny}
              endIcon={<KeyboardArrowDownRoundedIcon />}
              aria-controls={addMenuOpen ? "topbar-add-menu" : undefined}
              aria-haspopup="menu"
              aria-expanded={addMenuOpen ? "true" : undefined}
              sx={{
                ...shimmerSx,
                borderRadius: 999,
                textTransform: "none",
                fontWeight: 700,
                minWidth: 0,
                px: 1.25,
                py: 0.45,
                lineHeight: 1.2,
                minHeight: 30,
                bgcolor: addButtonBg,
                color: theme.palette.common.white,
                boxShadow: `0 10px 22px ${alpha(addButtonShadowColor, theme.palette.mode === "dark" ? 0.28 : 0.22)}`,
                transition: "all 180ms ease",
                "&:hover": {
                  bgcolor: addButtonHoverBg,
                  transform: "translateY(-1px)",
                  boxShadow: `0 14px 26px ${alpha(addButtonShadowColor, theme.palette.mode === "dark" ? 0.34 : 0.28)}`,
                },
              }}
            >
              {addButtonLabel}
            </Button>

            {isMailAdmin ? (
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
            ) : null}

            <IconButton
              size="medium"
              onClick={colorMode.toggleColorMode}
              aria-label={nextThemeLabel}
            >
              {theme.palette.mode === "dark" ? (
                <LightModeOutlinedIcon fontSize="medium" />
              ) : (
                <DarkModeOutlinedIcon fontSize="medium" />
              )}
            </IconButton>

            <IconButton
              size="medium"
              onClick={() => navigate("/config")}
              aria-label="Settings"
            >
              <SettingsOutlinedIcon fontSize="medium" />
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

      {isMailAdmin ? (
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
              borderColor: menuPaperBorder,
              bgcolor: alpha(theme.palette.background.paper, theme.palette.mode === "dark" ? 0.96 : 0.98),
              boxShadow:
                theme.palette.mode === "dark"
                  ? `0 18px 40px ${alpha(theme.palette.common.black, 0.46)}`
                  : `0 18px 36px ${alpha(colorTokens.primary[200], 0.22)}`,
            },
          }}
        >
          {notificationItems.length > 0 ? (
            <Box
              px={1.75}
              py={1.25}
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 1,
                borderBottom: "1px solid",
                borderColor:
                  theme.palette.mode === "dark"
                    ? "rgba(148,163,184,0.14)"
                    : "rgba(15,23,42,0.08)",
              }}
            >
              <Typography variant="subtitle2" fontWeight={700}>
                Notifications
              </Typography>
              {unreadCount > 0 ? (
                <Button
                  size="small"
                  onClick={handleMarkAllNotificationsAsRead}
                  sx={{
                    textTransform: "none",
                    fontWeight: 700,
                    minWidth: 0,
                    px: 0,
                    color: notificationAccent,
                  }}
                >
                  Mark all as read
                </Button>
              ) : null}
            </Box>
          ) : null}

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
                          ? unreadDotColor
                          : unreadDotColor,
                    flexShrink: 0,
                    mt: 0.9,
                    mr: 1.25,
                    border: item.__read ? "1px solid transparent" : "none",
                  }}
                />
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 1,
                    minWidth: 0,
                    width: "100%",
                  }}
                >
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
                  {!item.__read ? (
                    <Button
                      size="small"
                      onClick={(event) => handleMarkNotificationAsRead(event, item.id)}
                      sx={{
                        textTransform: "none",
                        fontWeight: 700,
                        minWidth: 0,
                        flexShrink: 0,
                        px: 0,
                        color: notificationAccent,
                      }}
                    >
                      Mark as read
                    </Button>
                  ) : null}
                </Box>
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
                    alpha(notificationAccent, theme.palette.mode === "dark" ? 0.42 : 0.24),
                  color: notificationAccent,
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? alpha(theme.palette.info.dark, 0.34)
                      : alpha(theme.palette.info.light, 0.95),
                  "&:hover": {
                    borderColor: alpha(notificationAccent, theme.palette.mode === "dark" ? 0.62 : 0.38),
                    bgcolor:
                      theme.palette.mode === "dark"
                        ? alpha(theme.palette.info.main, 0.26)
                        : alpha(theme.palette.info.light, 0.98),
                  },
                }}
              >
                See previous notifications
              </Button>
            </Box>
          ) : null}
        </Menu>
      ) : null}

      <Menu
        id="topbar-add-menu"
        anchorEl={addMenuAnchorEl}
        open={addMenuOpen}
        onClose={handleCloseAddMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{
          sx: addMenuPaperSx,
        }}
      >
        <MenuItem
          onClick={() => handleSelectAddAction("channel")}
          disabled={isAddingAny}
          sx={buildAddMenuItemSx(addChannelAccent)}
        >
          <ListItemIcon sx={buildAddMenuIconSx(addChannelAccent)}>
            <SmartDisplayRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary={addingChannel ? "Adding channel..." : "Add Channel"}
            secondary="Connect a YouTube channel"
            primaryTypographyProps={{ fontWeight: 700 }}
            secondaryTypographyProps={{ sx: { mt: 0.2 } }}
          />
        </MenuItem>
        <MenuItem
          onClick={() => handleSelectAddAction("gmail")}
          disabled={isAddingAny}
          sx={buildAddMenuItemSx(addGmailAccent)}
        >
          <ListItemIcon sx={buildAddMenuIconSx(addGmailAccent)}>
            <AlternateEmailRoundedIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary={addingMail ? "Adding Gmail..." : "Add Gmail"}
            secondary="Connect a Gmail inbox"
            primaryTypographyProps={{ fontWeight: 700 }}
            secondaryTypographyProps={{ sx: { mt: 0.2 } }}
          />
        </MenuItem>
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
