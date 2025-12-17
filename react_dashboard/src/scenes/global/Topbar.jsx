import { Box, IconButton, useTheme, Avatar } from "@mui/material";
import { useContext, useState } from "react";
import { ColorModeContext, tokens } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";

import InputBase from "@mui/material/InputBase";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import NotificationsOutlinedIcon from "@mui/icons-material/NotificationsOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import SearchIcon from "@mui/icons-material/Search";

const Topbar = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const colorMode = useContext(ColorModeContext);

  const { user } = useContext(UserContext);
  const [openProfile, setOpenProfile] = useState(false);

  return (
    <>
      <Box display="flex" justifyContent="space-between" p={2}>
        {/* SEARCH BAR */}
        <Box
          display="flex"
          backgroundColor={colors.primary[400]}
          borderRadius="3px"
        >
          <InputBase sx={{ ml: 2, flex: 1 }} placeholder="Search" />
          <IconButton sx={{ p: 1 }}>
            <SearchIcon />
          </IconButton>
        </Box>

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

          {/* SETTINGS / PROFILE */}
          <IconButton onClick={() => setOpenProfile(true)}>
            {user.avatar ? (
              <Avatar src={user.avatar} sx={{ width: 32, height: 32 }} />
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
