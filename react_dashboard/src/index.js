import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { BrowserRouter } from "react-router-dom";

import { CssBaseline, ThemeProvider } from "@mui/material";
import { ColorModeContext, useMode } from "./theme";
import { UserProvider } from "./context/UserContext";
import { useContext } from "react";
import { UserContext } from "./context/UserContext";

const root = ReactDOM.createRoot(document.getElementById("root"));

const ThemeShell = () => {
  const { user } = useContext(UserContext);
  const [theme, colorMode] = useMode(user?.id);
  return (
    <ColorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ThemeProvider>
    </ColorModeContext.Provider>
  );
};

const Root = () => (
  <React.StrictMode>
    <UserProvider>
      <ThemeShell />
    </UserProvider>
  </React.StrictMode>
);

root.render(<Root />);
