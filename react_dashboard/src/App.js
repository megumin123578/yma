import { memo, useState, useContext, useEffect } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import Topbar from "./scenes/global/Topbar";
import Sidebar from "./scenes/global/Sidebar";
import Dashboard from "./scenes/dashboard";
import Daily from "./scenes/content";
import AllChannelsScene from "./scenes/all_channels";
import TrafficSource from "./scenes/traffic_source";
import LoginPage from "./scenes/login";
import RegisterPage from "./scenes/register";
import SmmstoreScene from "./scenes/smmstore";
import ChannelCompareScene from "./scenes/channel_compare";
import RivalsData from "./scenes/rivals";

import {
  Box,
  Button,
  IconButton,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { ColorModeContext, tokens } from "./theme";
import GeographyScene from "./scenes/geography";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import SmartDisplayRoundedIcon from "@mui/icons-material/SmartDisplayRounded";
import AlternateEmailRoundedIcon from "@mui/icons-material/AlternateEmailRounded";
import KeyboardArrowDownRoundedIcon from "@mui/icons-material/KeyboardArrowDownRounded";
import { UserContext } from "./context/UserContext";
import SmmstoreAnalyticsScene from "./scenes/smmstore_analytics";
import AudienceAnalyticsScene from "./scenes/audience_analytics";
import ReachAnalyticsScene from "./scenes/reach_analytics";
import RevenueAnalyticsScene from "./scenes/revenue";
import MailMonitorScene from "./scenes/mail_monitor";
import ConfigPage from "./scenes/config";
import PrivacyPage from "./scenes/privacy";
import TermsPage from "./scenes/terms";
import LandingPage from "./scenes/landing";
import { AnimatePresence, motion } from "framer-motion";
import { startMailOAuth, uploadCredentials } from "./services/userService";

const DESKTOP_SIDEBAR_EXPANDED = "expanded";
const DESKTOP_SIDEBAR_COMPACT = "compact";
const DESKTOP_SIDEBAR_HIDDEN = "hidden";

const getNextDesktopSidebarMode = (currentMode) => {
  if (currentMode === DESKTOP_SIDEBAR_EXPANDED) return DESKTOP_SIDEBAR_COMPACT;
  if (currentMode === DESKTOP_SIDEBAR_COMPACT) return DESKTOP_SIDEBAR_HIDDEN;
  return DESKTOP_SIDEBAR_EXPANDED;
};

const ProtectedRoute = memo(function ProtectedRoute({ children, user, loading }) {
  if (loading) return null;
  if (!user) return <Navigate to="/" replace />;
  return children;
});

const AppRoutes = memo(function AppRoutes({ user, loading }) {
  return (
    <Routes>
      {/* Auth */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/terms" element={<TermsPage />} />

      {/* App */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/all_channels"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <AllChannelsScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/content"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <Daily />
          </ProtectedRoute>
        }
      />
      <Route
        path="/traffic_source"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <TrafficSource />
          </ProtectedRoute>
        }
      />
      <Route
        path="/geography"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <GeographyScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/channel_compare"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <ChannelCompareScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/rivals"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <RivalsData />
          </ProtectedRoute>
        }
      />
      <Route
        path="/smmstore"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <SmmstoreScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/smmstore_analytics"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <SmmstoreAnalyticsScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audience_analytics"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <AudienceAnalyticsScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reach"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <ReachAnalyticsScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/revenue"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <RevenueAnalyticsScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/mail_monitor"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <MailMonitorScene />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config"
        element={
          <ProtectedRoute user={user} loading={loading}>
            <ConfigPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
});

function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const colorMode = useContext(ColorModeContext);
  const [desktopSidebarMode, setDesktopSidebarMode] = useState(DESKTOP_SIDEBAR_EXPANDED);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [addingChannel, setAddingChannel] = useState(false);
  const [addingMail, setAddingMail] = useState(false);
  const [addMenuAnchorEl, setAddMenuAnchorEl] = useState(null);
  const location = useLocation();
  const { user, loading } = useContext(UserContext);
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
  const addMenuPaperBorder = alpha(theme.palette.divider, theme.palette.mode === "dark" ? 0.3 : 0.7);
  const addMenuPaperBg = alpha(
    theme.palette.background.paper,
    theme.palette.mode === "dark" ? 0.94 : 0.98
  );
  const addMenuPaperShadow =
    theme.palette.mode === "dark"
      ? `0 22px 44px ${alpha(theme.palette.common.black, 0.46)}`
      : `0 22px 44px ${alpha(colorTokens.primary[200], 0.18)}`;
  const addChannelAccent = theme.palette.error.main;
  const addGmailAccent = colorTokens.redAccent[400];
  const addMenuPaperSx = {
    mt: 1,
    minWidth: 284,
    borderRadius: 3,
    overflow: "hidden",
    border: "1px solid",
    borderColor: addMenuPaperBorder,
    bgcolor: addMenuPaperBg,
    backdropFilter: "blur(14px)",
    WebkitBackdropFilter: "blur(14px)",
    boxShadow: addMenuPaperShadow,
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

  const noLayoutRoutes = [
    "/",
    "/login",
    "/register",
    "/privacy",
    "/terms",
  ];
  const isNoLayout = noLayoutRoutes.includes(location.pathname);

  useEffect(() => {
    if (isMobile) {
      setIsMobileSidebarOpen(false);
    }
  }, [isMobile, location.pathname]);

  const handleToggleSidebar = () => {
    if (isMobile) {
      setIsMobileSidebarOpen((current) => !current);
      return;
    }
    setDesktopSidebarMode((current) => getNextDesktopSidebarMode(current));
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

  return (
    <div className="app">
      {!isNoLayout && (
        <Sidebar
          desktopSidebarMode={desktopSidebarMode}
          isMobileSidebarOpen={isMobileSidebarOpen}
          setIsMobileSidebarOpen={setIsMobileSidebarOpen}
          isMobile={isMobile}
        />
      )}

      <main className="content">
        {!isNoLayout && (
          <Topbar
            onToggleSidebar={handleToggleSidebar}
            desktopSidebarMode={desktopSidebarMode}
            isMobile={isMobile}
          />
        )}
        {isNoLayout && (
          <Box display="flex" justifyContent="flex-end" alignItems="center" gap={1} pt={0} px={2}>
            <Button
              variant="contained"
              size="small"
              onClick={handleOpenAddMenu}
              disabled={isAddingAny}
              endIcon={<KeyboardArrowDownRoundedIcon />}
              aria-controls={addMenuOpen ? "app-add-menu" : undefined}
              aria-haspopup="menu"
              aria-expanded={addMenuOpen ? "true" : undefined}
              sx={{
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
            <IconButton onClick={colorMode.toggleColorMode} aria-label={nextThemeLabel}>
              {theme.palette.mode === "dark" ? (
                <LightModeOutlinedIcon />
              ) : (
                <DarkModeOutlinedIcon />
              )}
            </IconButton>
            <Menu
              id="app-add-menu"
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
          </Box>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            style={{ minHeight: 0 }}
          >
            <AppRoutes user={user} loading={loading} />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}

export default App;
