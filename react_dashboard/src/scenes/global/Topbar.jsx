import { Box, IconButton, useTheme, Avatar } from "@mui/material";
import { useContext, useState } from "react";
import { ColorModeContext, tokens } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";

import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import NotificationsOutlinedIcon from "@mui/icons-material/NotificationsOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";

const Topbar = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const colorMode = useContext(ColorModeContext);

  const { user } = useContext(UserContext);
  const [openProfile, setOpenProfile] = useState(false);

  // ✅ GUARD: chưa login
  const avatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? `${process.env.REACT_APP_API_URL || ""}${user.avatar}`
      : null;

  return (
    <>
      <Box display="flex" justifyContent="flex-end" p={2}>

        {/* ICONS */}
        <Box display="flex" alignItems="center">
          <IconButton onClick={colorMode.toggleColorMode}>
            {theme.palette.mode === "dark" ? (
              <DarkModeOutlinedIcon />
            ) : (
              <LightModeOutlinedIcon />
            )}
          </IconButton>

          <IconButton>
            <NotificationsOutlinedIcon />
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

      {/* PROFILE SETTING DIALOG */}
      <ProfileDialog
        open={openProfile}
        onClose={() => setOpenProfile(false)}
      />
    </>
  );
};

export default Topbar;
