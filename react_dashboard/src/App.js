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

import { CssBaseline, ThemeProvider } from "@mui/material";
import { ColorModeContext, useMode } from "./theme";
import GeographyChart from "./components/Geography";
import { UserContext } from "./context/UserContext";

function App() {
  const [theme, colorMode] = useMode();
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
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />

        <div className="app">
          {!isNoLayout && <Sidebar isSidebar={isSidebar} />}

          <main className="content">
            {!isNoLayout && <Topbar setIsSidebar={setIsSidebar} />}

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
            </Routes>
          </main>
        </div>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export default App;
