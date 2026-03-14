import { Box, IconButton, useTheme, Avatar } from "@mui/material";
import { useContext, useState } from "react";
import { ColorModeContext } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";
import CredentialsDialog from "../../components/dialogs/CredentialsDialog";

import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import SettingsIcon from '@mui/icons-material/Settings';
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";

const Topbar = ({ setIsSidebar, isMobile = false }) => {
  const theme = useTheme();
  // const colors = tokens(theme.palette.mode);
  const colorMode = useContext(ColorModeContext);

  const { user } = useContext(UserContext);
  const [openProfile, setOpenProfile] = useState(false);
  const [openCredentials, setOpenCredentials] = useState(false);

  // GUARD: chưa login
  const avatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? `${process.env.REACT_APP_API_URL || ""}${user.avatar}`
      : null;

  return (
    <>
      <Box display="flex" justifyContent="flex-end" p={2}>

        {/* ICONS */}
        <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
          {isMobile ? (
            <IconButton onClick={() => setIsSidebar?.((prev) => !prev)}>
              <MenuOutlinedIcon />
            </IconButton>
          ) : (
            <Box />
          )}
          <Box display="flex" alignItems="center">
          <IconButton onClick={colorMode.toggleColorMode}>
            {theme.palette.mode === "dark" ? (
              <DarkModeOutlinedIcon />
            ) : (
              <LightModeOutlinedIcon />
            )}
          </IconButton>

          <IconButton
            aria-label="Help"
            onClick={() => window.open("/help.pdf", "_blank", "noopener,noreferrer")}
          >
            <HelpOutlineIcon />
          </IconButton>

          <IconButton onClick={() => setOpenCredentials(true)}>
            <SettingsIcon />
          </IconButton>

          {/* PROFILE */}
          <IconButton onClick={() => setOpenProfile(true)}>
            {avatarSrc ? (
              <Avatar src={avatarSrc} sx={{ width: 32, height: 32 }} />
            ) : (
              <PersonOutlinedIcon />
            )}
          </IconButton>
          </Box>
        </Box>
      </Box>

      {/* PROFILE SETTING DIALOG */}
      <ProfileDialog
        open={openProfile}
        onClose={() => setOpenProfile(false)}
      />

      <CredentialsDialog
        open={openCredentials}
        onClose={() => setOpenCredentials(false)}
      />
    </>
  );
};

export default Topbar;
