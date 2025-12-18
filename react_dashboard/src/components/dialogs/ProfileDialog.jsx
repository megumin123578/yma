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
  useTheme,
} from "@mui/material";
import { useContext, useEffect, useState, forwardRef } from "react";
import { UserContext } from "../../context/UserContext";
import PhotoCameraIcon from "@mui/icons-material/PhotoCamera";
import ExitToAppIcon from "@mui/icons-material/ExitToApp";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";
import ChangePasswordDialog from "./ChangePasswordDialog";
import { logout } from "../../services/authService";
import { uploadAvatar } from "../../services/userService";
import { useNavigate } from "react-router-dom";

const Transition = forwardRef(function Transition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const ProfileDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const { user, setUser } = useContext(UserContext);
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [pendingAvatar, setPendingAvatar] = useState(null); // File chưa upload
  const [previewAvatar, setPreviewAvatar] = useState(null);
  const [openPassword, setOpenPassword] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && user) {
      setName(user.name || "");
      setPreviewAvatar(user.avatar || null);
      setPendingAvatar(null);
    }
  }, [open, user]);

  // 👉 Chỉ chọn ảnh → preview
  const handleSelectAvatar = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setPendingAvatar(file);
    setPreviewAvatar(URL.createObjectURL(file));
  };

  const handleSave = async () => {
    if (!user) {
      console.error("User is null, cannot save profile");
      return; // 🔴 CHẶN NGAY
    }

    if (saving) return;
    setSaving(true);

    try {
      let avatarUrl = user.avatar || null;

      if (pendingAvatar) {
        const res = await uploadAvatar(pendingAvatar);
        avatarUrl = res.data.avatarUrl;
      }

      setUser((prev) => ({
        ...prev,
        name,
        avatar: avatarUrl,
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
      slots={{ transition: Transition }}
      slotProps={{
        paper: {
          sx: {
            borderRadius: 3,
            width: 380,
            backgroundColor: theme.palette.background.paper,
          },
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h5" component="span" fontWeight="bold">
          Profile Settings
        </Typography>
      </DialogTitle>

      <DialogContent>
        <Fade in={open}>
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            gap={2.5}
            mt={1}
          >
            {/* AVATAR */}
            <Box position="relative">
              <Avatar
                src={
                  previewAvatar
                    ? `${process.env.REACT_APP_API_URL || ""}${previewAvatar}`
                    : undefined
                }
                sx={{ width: 96, height: 96, boxShadow: 3 }}
              />

              <IconButton
                component="label"
                sx={{
                  position: "absolute",
                  bottom: -6,
                  right: -6,
                  backgroundColor: theme.palette.primary.main,
                  color: "#fff",
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
            />

            {/* ACTIONS */}
            <Box display="flex" flexDirection="column" gap={1.5} width="100%">
              <Box display="flex" gap={1}>
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={onClose}
                  disabled={saving}
                >
                  Cancel
                </Button>

                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? "Saving..." : "Save"}
                </Button>
              </Box>

              <Button
                startIcon={<LockOutlinedIcon />}
                variant="text"
                onClick={() => setOpenPassword(true)}
              >
                Change Password
              </Button>

              <Button
                startIcon={<ExitToAppIcon />}
                variant="text"
                onClick={handleLogout}
                sx={{ color: theme.palette.error.main }}
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
