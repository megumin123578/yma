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

import { Box, Button, IconButton, useMediaQuery, useTheme } from "@mui/material";
import { ColorModeContext } from "./theme";
import GeographyScene from "./scenes/geography";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
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
  const location = useLocation();
  const { user, loading } = useContext(UserContext);

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
              onClick={handleAddChannel}
              disabled={addingChannel}
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
              Add Channel
            </Button>
            <Button
              variant="contained"
              size="small"
              onClick={handleAddGmail}
              disabled={addingMail}
              sx={{
                borderRadius: 999,
                textTransform: "none",
                fontWeight: 700,
                minWidth: 0,
                px: 1.25,
                py: 0.45,
                lineHeight: 1.2,
                minHeight: 30,
                bgcolor: theme.palette.mode === "dark" ? "#b45309" : "#ea4335",
                color: "#fff",
                boxShadow:
                  theme.palette.mode === "dark"
                    ? "0 10px 22px rgba(180,83,9,0.28)"
                    : "0 10px 22px rgba(234,67,53,0.22)",
                transition: "all 180ms ease",
                "&:hover": {
                  bgcolor: theme.palette.mode === "dark" ? "#92400e" : "#d93025",
                  transform: "translateY(-1px)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 26px rgba(180,83,9,0.34)"
                      : "0 14px 26px rgba(234,67,53,0.28)",
                },
              }}
            >
              {addingMail ? "Adding..." : "Add Gmail"}
            </Button>
            <IconButton onClick={colorMode.toggleColorMode}>
              {theme.palette.mode === "dark" ? (
                <DarkModeOutlinedIcon />
              ) : (
                <LightModeOutlinedIcon />
              )}
            </IconButton>
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
