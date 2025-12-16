import { useState } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
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

function App() {
  const [theme, colorMode] = useMode();
  const [isSidebar, setIsSidebar] = useState(true);
  const location = useLocation();

  const noLayoutRoutes = ["/", "/register", "/forgot-password"];
  const isNoLayout = noLayoutRoutes.includes(location.pathname);

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
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/content" element={<Daily />} />
              <Route path="/traffic_source" element={<TrafficSource />} />
              <Route path="/geography" element={<GeographyChart />} />
            </Routes>
          </main>
        </div>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
}

export default App;
