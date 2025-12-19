import { useState, useContext } from "react";
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

import { Box, IconButton, useTheme } from "@mui/material";
import { ColorModeContext } from "./theme";
import GeographyChart from "./components/Geography";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import { UserContext } from "./context/UserContext";

function App() {
  const theme = useTheme();
  const colorMode = useContext(ColorModeContext);
  const [isSidebar, setIsSidebar] = useState(true);
  const location = useLocation();
  const { user, loading } = useContext(UserContext);

  const noLayoutRoutes = ["/", "/register", "/forgot-password"];
  const isNoLayout = noLayoutRoutes.includes(location.pathname);

  const ProtectedRoute = ({ children }) => {
    if (loading) return null; // Wait for auth check
    if (!user) return <Navigate to="/" replace />;
    return children;
  };

  return (
    <div className="app">
      {!isNoLayout && <Sidebar isSidebar={isSidebar} />}

      <main className="content">
        {!isNoLayout && <Topbar setIsSidebar={setIsSidebar} />}
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

        <Routes>
          {/* Auth */}
          <Route path="/" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />

          {/* App */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/content"
            element={
              <ProtectedRoute>
                <Daily />
              </ProtectedRoute>
            }
          />
          <Route
            path="/traffic_source"
            element={
              <ProtectedRoute>
                <TrafficSource />
              </ProtectedRoute>
            }
          />
          <Route
            path="/geography"
            element={
              <ProtectedRoute>
                <GeographyChart />
              </ProtectedRoute>
            }
          />
          <Route
            path="/smmstore"
            element={
              <ProtectedRoute>
                <SmmstoreScene />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </div>
  );
}

export default App;
