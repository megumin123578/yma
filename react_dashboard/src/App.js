import { memo, useState, useContext, useEffect } from "react";
import { Routes, Route, useLocation, Navigate } from "react-router-dom";
import Topbar from "./scenes/global/Topbar";
import Sidebar from "./scenes/global/Sidebar";
import Dashboard from "./scenes/dashboard";
import Daily from "./scenes/content";
import TrafficSource from "./scenes/traffic_source";
import LoginPage from "./scenes/login";
import RegisterPage from "./scenes/register";
import ForgotPasswordPage from "./scenes/forgot_password";
import SmmstoreScene from "./scenes/smmstore";
import ChannelCompareScene from "./scenes/channel_compare";
import RivalsData from "./scenes/rivals";

import { Box, IconButton, useMediaQuery, useTheme } from "@mui/material";
import { ColorModeContext } from "./theme";
import GeographyScene from "./scenes/geography";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import { UserContext } from "./context/UserContext";
import SmmstoreAnalyticsScene from "./scenes/smmstore_analytics";
import AudienceAnalyticsScene from "./scenes/audience_analytics";
import ReachAnalyticsScene from "./scenes/reach_analytics";
import RevenueAnalyticsScene from "./scenes/revenue";
import ConfigPage from "./scenes/config";
import PrivacyPage from "./scenes/privacy";
import TermsPage from "./scenes/terms";
import LandingPage from "./scenes/landing";

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
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
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
        path="smmstore_analytics"
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
  const location = useLocation();
  const { user, loading } = useContext(UserContext);

  const noLayoutRoutes = [
    "/",
    "/login",
    "/register",
    "/forgot-password",
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
          <Box display="flex" justifyContent="flex-end" pt={0} px={2}>
            <IconButton onClick={colorMode.toggleColorMode}>
              {theme.palette.mode === "dark" ? (
                <DarkModeOutlinedIcon />
              ) : (
                <LightModeOutlinedIcon />
              )}
            </IconButton>
          </Box>
        )}

        <AppRoutes user={user} loading={loading} />
      </main>
    </div>
  );
}

export default App;
