import { Box, IconButton, useTheme, Avatar, Button, Typography } from "@mui/material";
import { useContext, useState } from "react";
import { ColorModeContext } from "../../theme";
import { UserContext } from "../../context/UserContext";
import ProfileDialog from "../../components/dialogs/ProfileDialog";
import { uploadCredentials } from "../../services/userService";

import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import PersonOutlinedIcon from "@mui/icons-material/PersonOutlined";
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";

const Topbar = ({ setIsSidebar, isSidebar, isMobile = false }) => {
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
  const shimmerSx = {
    position: "relative",
    overflow: "hidden",
    "&:before": {
      content: '""',
      position: "absolute",
      top: "-50%",
      left: "-120%",
      width: "80%",
      height: "200%",
      background:
        "linear-gradient(120deg, transparent 0%, rgba(255,255,255,0.45) 45%, transparent 90%)",
      transform: "translateX(0)",
      transition: "transform 0.7s ease",
      opacity: 0.8,
      pointerEvents: "none",
    },
    "&:hover:before": {
      transform: "translateX(260%)",
    },
  };

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
      <Box
        display="flex"
        justifyContent="flex-end"
        px={2}
        py={1.25}
        sx={{
          position: "sticky",
          top: 0,
          zIndex: 1100,
          bgcolor: theme.palette.mode === "dark"
            ? "rgba(17, 24, 39, 0.82)"
            : "rgba(255, 255, 255, 0.82)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >

        {/* ICONS */}
        <Box display="flex" alignItems="center" justifyContent="space-between" width="100%">
          <Box display="flex" alignItems="center">
            <IconButton
              size="medium"
              onClick={() => setIsSidebar?.((prev) => !prev)}
              sx={{ mr: 1 }}
            >
              <MenuOutlinedIcon fontSize="medium" />
            </IconButton>
            <Typography
              variant="h5"
              sx={{
                fontSize: { xs: "1rem", sm: "1.1rem" },
                fontWeight: 800,
                lineHeight: 1.2,
                whiteSpace: "nowrap",
              }}
            >
              YT Manage App
            </Typography>
          </Box>
          <Box display="flex" alignItems="center">
            <Button
              variant="contained"
              size="small"
              onClick={handleAddChannel}
              disabled={addingChannel}
              sx={{
                ...shimmerSx,
                mx: 1,
                borderRadius: 999,
                textTransform: "none",
                fontWeight: 700,
                minWidth: 0,
                px: 1.25,
                py: 0.45,
                lineHeight: 1.2,
                minHeight: 30,
                bgcolor: theme.palette.mode === "dark" ? "#2b8a7b" : theme.palette.primary.main,
                color: "#fff",
                boxShadow:
                  theme.palette.mode === "dark"
                    ? "0 10px 22px rgba(43,138,123,0.28)"
                    : "0 10px 22px rgba(25,118,210,0.22)",
                transition: "all 180ms ease",
                "&:hover": {
                  bgcolor: theme.palette.mode === "dark" ? "#247468" : theme.palette.primary.dark,
                  transform: "translateY(-1px)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 14px 26px rgba(43,138,123,0.34)"
                      : "0 14px 26px rgba(25,118,210,0.28)",
                },
              }}
            >
              Add Channel
            </Button>

            <IconButton size="medium" onClick={colorMode.toggleColorMode}>
              {theme.palette.mode === "dark" ? (
                <DarkModeOutlinedIcon fontSize="medium" />
              ) : (
                <LightModeOutlinedIcon fontSize="medium" />
              )}
            </IconButton>

            {/* PROFILE */}
            <IconButton size="medium" onClick={() => setOpenProfile(true)}>
              {avatarSrc ? (
                <Avatar src={avatarSrc} sx={{ width: 32, height: 32 }} />
              ) : (
                <PersonOutlinedIcon fontSize="medium" />
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
