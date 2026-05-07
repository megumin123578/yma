import {
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  Button,
  Avatar,
  Box,
  Fade,
  Slide,
  Typography,
  IconButton,
  InputAdornment,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { useContext, useEffect, useState, forwardRef } from "react";
import { UserContext } from "../../context/UserContext";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import ExitToAppIcon from "@mui/icons-material/ExitToApp";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import ChangePasswordDialog from "./ChangePasswordDialog";
import { logout } from "../../services/authService";
import { uploadAvatar, updateProfile } from "../../services/userService";
import { useNavigate } from "react-router-dom";
import { resolveApiAssetUrl } from "../../config";

const Transition = forwardRef(function Transition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const maskApiKey = (value, visibleStart = 4, visibleEnd = 4) => {
  if (!value) return "";
  const trimmed = String(value);
  if (trimmed.length <= visibleStart + visibleEnd) return trimmed;
  const maskedLength = trimmed.length - visibleStart - visibleEnd;
  return `${trimmed.slice(0, visibleStart)}${"*".repeat(maskedLength)}${trimmed.slice(-visibleEnd)}`;
};

const ProfileDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const isDark = theme.palette.mode === "dark";
  const paperBg = isDark
    ? "linear-gradient(180deg, #1e1e2f, #1a1a27)"
    : theme.palette.background.paper;
  const titleColor = isDark ? "#fff" : theme.palette.text.primary;
  const subtitleColor = isDark
    ? "rgba(255,255,255,0.65)"
    : theme.palette.text.secondary;
  const labelColor = isDark ? "#bdbdbd" : theme.palette.text.secondary;
  const inputColor = isDark ? "#fff" : theme.palette.text.primary;
  const borderColor = isDark ? "#555" : "#d0d0d0";
  const hoverBorder = isDark ? "#90caf9" : theme.palette.primary.main;

  const { user, setUser } = useContext(UserContext);
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [smmstoreApiKey, setSmmstoreApiKey] = useState("");
  const [pendingAvatar, setPendingAvatar] = useState(null); // File chưa upload
  const [previewAvatar, setPreviewAvatar] = useState(null);
  const [openPassword, setOpenPassword] = useState(false);
  const [saving, setSaving] = useState(false);
  const [isEditingApiKey, setIsEditingApiKey] = useState(false);

  useEffect(() => {
    if (open && user) {
      setName(user.name || "");
      setSmmstoreApiKey(user.smmstore_api_key || "");
      setPreviewAvatar(user.avatar || null);
      setPendingAvatar(null);
      setIsEditingApiKey(false);
    }
  }, [open, user]);

  const handleSelectAvatar = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setPendingAvatar(file);
    setPreviewAvatar(URL.createObjectURL(file));
  };

  const handleSave = async () => {
    if (!user) {
      console.error("User is null, cannot save profile");
      return;
    }

    if (saving) return;
    setSaving(true);

    try {
      let avatarUrl = user.avatar || null;

      if (pendingAvatar) {
        const res = await uploadAvatar(pendingAvatar);
        avatarUrl = res.data.avatarUrl;
      }

      const updatedUser = await updateProfile({
        name,
        smmstore_api_key: smmstoreApiKey,
      });

      setUser((prev) => ({
        ...prev,
        ...updatedUser,
        name: updatedUser.name,
        smmstore_api_key: updatedUser.smmstore_api_key ?? smmstoreApiKey,
        // Prefer freshly uploaded avatar if any
        avatar: avatarUrl ?? updatedUser.avatar ?? prev?.avatar ?? null,
      }));

      onClose();
    } catch (err) {
      console.error("Save profile failed:", err);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    setUser(null);
    navigate("/", { replace: true });
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      keepMounted
      fullScreen={isMobile}
      slots={{ transition: Transition }}
      slotProps={{
        paper: {
          sx: {
            width: { xs: "100vw", sm: 420 },
            maxWidth: { xs: "100vw", sm: 420 },
            borderRadius: { xs: 0, sm: 4 },
            background: paperBg,
            boxShadow: isDark
              ? "0 20px 50px rgba(0,0,0,0.45)"
              : "0 12px 30px rgba(0,0,0,0.15)",
            color: inputColor,
          },
        },
      }}
    >
      <DialogTitle component='div'>
        <Typography variant="h5" fontWeight="bold" color={titleColor}>
          Profile Settings
        </Typography>
        <Typography
          variant="body2"
          color={subtitleColor}
          mt={0.5}
        >
          Manage your personal information
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ px: { xs: 2, sm: 3 } }}>
        <Fade in={open}>
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            gap={3}
            mt={1}
          >
            {/* AVATAR */}
            <Box position="relative">
              <Avatar
                src={
                  previewAvatar
                    ? resolveApiAssetUrl(previewAvatar)
                    : undefined
                }
                sx={{
                  width: 96,
                  height: 96,
                  boxShadow: "0 10px 30px rgba(0,0,0,0.6)",
                  border: "2px solid #2f80ed",
                }}
              />

              <IconButton
                component="label"
                sx={{
                  position: "absolute",
                  bottom: -6,
                  right: -6,
                  background: "linear-gradient(90deg, #42a5f5, #478ed1)",
                  color: "#fff",
                  boxShadow: "0 6px 18px rgba(66,165,245,0.5)",
                  "&:hover": {
                    background: "linear-gradient(90deg, #64b5f6, #5e92f3)",
                  },
                }}
              >
                <PhotoCameraIcon fontSize="small" />
                <input
                  hidden
                  type="file"
                  accept="image/*"
                  onChange={handleSelectAvatar}
                />
              </IconButton>
            </Box>

            {/* NAME */}
            <TextField
              fullWidth
              label="Display Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              slotProps={{ inputLabel: {style: { color: labelColor }} }}
              InputProps={{ style: { color: inputColor } }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 2,
                  "& fieldset": { borderColor },
                  "&:hover fieldset": { borderColor: hoverBorder },
                  "&.Mui-focused fieldset": { borderColor: hoverBorder },
                },
              }}
            />

            {/* SMM STORE API KEY */}
            <TextField
              fullWidth
              label="SMM Store API Key"
              value={
                isEditingApiKey ? smmstoreApiKey : maskApiKey(smmstoreApiKey)
              }
              onChange={(e) => {
                if (isEditingApiKey) setSmmstoreApiKey(e.target.value);
              }}
              type={isEditingApiKey ? "password" : "text"}
              slotProps={{ inputLabel: {style: { color: labelColor }} }}
              InputProps={{
                style: { color: inputColor },
                readOnly: !isEditingApiKey,
                endAdornment: (
                  <InputAdornment position="end">
                    <Button
                      size="small"
                      variant="text"
                      onClick={() =>
                        setIsEditingApiKey((prev) => !prev)
                      }
                      sx={{ minWidth: 0, px: 1, color: labelColor }}
                    >
                      {isEditingApiKey ? "Done" : "Edit"}
                    </Button>
                  </InputAdornment>
                ),
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 2,
                  "& fieldset": { borderColor },
                  "&:hover fieldset": { borderColor: hoverBorder },
                  "&.Mui-focused fieldset": { borderColor: hoverBorder },
                },
              }}
            />

            {/* ACTIONS */}
            <Box display="flex" flexDirection="column" gap={1.5} width="100%">
              <Box display="flex" gap={1}>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={onClose}
                  disabled={saving}
                  sx={{
                    color: inputColor,
                    borderColor,
                    "&:hover": {
                      borderColor: hoverBorder,
                      backgroundColor: isDark
                        ? "rgba(144,202,249,0.08)"
                        : "rgba(0,0,0,0.03)",
                    },
                  }}
                >
                  Cancel
                </Button>

                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleSave}
                  disabled={saving}
                  sx={{
                    fontWeight: 600,
                    background: "linear-gradient(90deg, #42a5f5, #478ed1)",
                    "&:hover": {
                      background:
                        "linear-gradient(90deg, #64b5f6, #5e92f3)",
                      boxShadow: "0 10px 25px rgba(66,165,245,0.4)",
                    },
                  }}
                >
                  {saving ? "Saving..." : "Save"}
                </Button>
              </Box>

              <Button
                startIcon={<LockOutlinedIcon />}
                variant="text"
                onClick={() => setOpenPassword(true)}
                sx={{
                  color: isDark ? "#90caf9" : theme.palette.primary.main,
                  justifyContent: "flex-start",
                  "&:hover": {
                    backgroundColor: isDark
                      ? "rgba(144,202,249,0.08)"
                      : "rgba(0,0,0,0.04)",
                  },
                }}
              >
                Change Password
              </Button>

              <Button
                startIcon={<ExitToAppIcon />}
                variant="text"
                onClick={handleLogout}
                sx={{
                  color: "#ef5350",
                  justifyContent: "flex-start",
                  "&:hover": {
                    backgroundColor: "rgba(239,83,80,0.08)",
                  },
                }}
              >
                Logout
              </Button>
            </Box>

            <ChangePasswordDialog
              open={openPassword}
              onClose={() => setOpenPassword(false)}
            />
          </Box>
        </Fade>
      </DialogContent>
    </Dialog>

  );
};

export default ProfileDialog;
