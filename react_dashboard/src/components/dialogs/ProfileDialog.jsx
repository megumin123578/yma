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
import { useNavigate } from "react-router-dom";

const Transition = forwardRef(function Transition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const ProfileDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const { user, setUser } = useContext(UserContext);
  const [name, setName] = useState(user.name || "");
  const [openPassword, setOpenPassword] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) setName(user.name || "");
  }, [open, user.name]);

  const handleAvatarUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () =>
      setUser((prev) => ({ ...prev, avatar: reader.result }));
    reader.readAsDataURL(file);
  };

  const handleSave = () => {
    setUser((prev) => ({ ...prev, name }));
    onClose();
  };

  const handleLogout = () => {
    logout();
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
            backgroundColor: theme.palette.background.paper, // ✅ nền sáng hơn
          },
        },
      }}
    >
      {/* TITLE */}
      <DialogTitle>
        <Typography
          variant="h5"
          fontWeight="bold"
          component="div"
          color={theme.palette.text.primary} // ✅ chữ rõ
        >
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
                src={user.avatar}
                sx={{
                  width: 96,
                  height: 96,
                  boxShadow: 3,
                }}
              />

              <IconButton
                component="label"
                sx={{
                  position: "absolute",
                  bottom: -6,
                  right: -6,
                  backgroundColor: theme.palette.primary.main,
                  color: "#fff",
                  "&:hover": {
                    backgroundColor: theme.palette.primary.dark,
                  },
                }}
              >
                <PhotoCameraIcon fontSize="small" />
                <input
                  hidden
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarUpload}
                />
              </IconButton>
            </Box>

            {/* NAME INPUT */}
            <TextField
              fullWidth
              label="Display Name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              InputLabelProps={{
                sx: { color: theme.palette.text.secondary },
              }}
              inputProps={{
                sx: { color: theme.palette.text.primary },
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  "& fieldset": {
                    borderColor: theme.palette.divider,
                  },
                  "&:hover fieldset": {
                    borderColor: theme.palette.primary.light,
                  },
                  "&.Mui-focused fieldset": {
                    borderColor: theme.palette.primary.main,
                  },
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
                  sx={{
                    color: theme.palette.text.primary,
                    borderColor: theme.palette.divider,
                  }}
                >
                  Cancel
                </Button>

                <Button
                  fullWidth
                  variant="contained"
                  onClick={handleSave}
                  sx={{ color: "#fff" }}
                >
                  Save
                </Button>
              </Box>

              <Button
                startIcon={<LockOutlinedIcon />}
                variant="text"
                onClick={() => setOpenPassword(true)}
                sx={{
                  justifyContent: "flex-start",
                  color: theme.palette.text.primary, // ✅ rõ
                }}
              >
                Change Password
              </Button>

              <Button
                startIcon={<ExitToAppIcon />}
                variant="text"
                onClick={handleLogout}
                sx={{
                  justifyContent: "flex-start",
                  color: theme.palette.error.main, // ✅ đỏ rõ ràng
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
