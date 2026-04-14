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
import { ColorModeContext } from "./theme";
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
  const [isSidebar, setIsSidebar] = useState(!isMobile);
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
  const addMenuPaperSx = {
    mt: 1,
    minWidth: 284,
    borderRadius: 3,
    overflow: "hidden",
    border: "1px solid",
    borderColor:
      theme.palette.mode === "dark"
        ? alpha("#e2e8f0", 0.14)
        : alpha("#0f172a", 0.08),
    bgcolor:
      theme.palette.mode === "dark"
        ? alpha("#0f172a", 0.94)
        : alpha("#ffffff", 0.98),
    backdropFilter: "blur(14px)",
    WebkitBackdropFilter: "blur(14px)",
    boxShadow:
      theme.palette.mode === "dark"
        ? "0 22px 44px rgba(2,6,23,0.46)"
        : "0 22px 44px rgba(15,23,42,0.14)",
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
    setIsSidebar((prev) => (isMobile ? false : prev));
  }, [isMobile]);

  useEffect(() => {
    if (isMobile) {
      setIsSidebar(false);
    }
  }, [location.pathname, isMobile]);

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
          isSidebar={isSidebar}
          setIsSidebar={setIsSidebar}
          isMobile={isMobile}
        />
      )}

      <main className="content">
        {!isNoLayout && (
          <Topbar
            setIsSidebar={setIsSidebar}
            isSidebar={isSidebar}
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
                sx={buildAddMenuItemSx("#ff0033")}
              >
                <ListItemIcon sx={buildAddMenuIconSx("#ff0033")}>
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
                sx={buildAddMenuItemSx("#ea4335")}
              >
                <ListItemIcon sx={buildAddMenuIconSx("#ea4335")}>
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
