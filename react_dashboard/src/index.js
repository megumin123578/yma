import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import { BrowserRouter } from "react-router-dom";

import { CssBaseline, ThemeProvider } from "@mui/material";
import { ColorModeContext, useMode } from "./theme";
import { UserProvider } from "./context/UserContext";

const root = ReactDOM.createRoot(document.getElementById("root"));

const Root = () => {
  const [theme, colorMode] = useMode();

  return (
    <React.StrictMode>
      <ColorModeContext.Provider value={colorMode}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            <UserProvider>
              <App />
            </UserProvider>
          </BrowserRouter>
        </ThemeProvider>
      </ColorModeContext.Provider>
    </React.StrictMode>
  );
};

root.render(<Root />);
