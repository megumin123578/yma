import { Box, IconButton, useTheme, Avatar, Button } from "@mui/material";
import { useContext, useState } from "react";
import { ColorModeContext } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";
import { uploadCredentials } from "../../services/userService";

import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import AddIcon from "@mui/icons-material/Add";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";

const Topbar = ({ setIsSidebar, isMobile = false }) => {
  const theme = useTheme();
  // const colors = tokens(theme.palette.mode);
  const colorMode = useContext(ColorModeContext);

  const { user } = useContext(UserContext);
  const [openProfile, setOpenProfile] = useState(false);
  const [addingChannel, setAddingChannel] = useState(false);

  // GUARD: chưa login
  const avatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? `${process.env.REACT_APP_API_URL || ""}${user.avatar}`
      : null;

  const handleAddChannel = async () => {
    if (addingChannel) return;
    setAddingChannel(true);
    try {
      const data = await uploadCredentials("");
      const nextUrl = data?.auth_url || "";
      if (nextUrl) {
        window.open(nextUrl, "_blank", "noopener");
      }
    } finally {
      setAddingChannel(false);
    }
  };

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

          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon fontSize="small" />}
            onClick={handleAddChannel}
            disabled={addingChannel}
            sx={{
              mx: 1,
              borderRadius: 999,
              textTransform: "none",
              fontWeight: 700,
              minWidth: 0,
              px: 1.5,
            }}
          >
            Add Channel
          </Button>

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
    </>
  );
};

export default Topbar;
