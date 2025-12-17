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

const Transition = forwardRef(function Transition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const ProfileDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const { user, setUser } = useContext(UserContext);
  const [name, setName] = useState(user.name || "");

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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      slots={{
        transition: Transition,
      }}
      keepMounted
      slotProps={{
        paper: {
        sx: {
            borderRadius: 3,
            width: 380,
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
                style: {
                  color: theme.palette.text.secondary, // ✅ label rõ
                },
              }}
              inputProps={{
                style: {
                  color: theme.palette.text.primary, // ✅ text rõ
                },
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
            <Box display="flex" gap={1} width="100%">
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
                sx={{
                  color: "#fff",
                }}
              >
                Save
              </Button>
            </Box>
          </Box>
        </Fade>
      </DialogContent>
    </Dialog>
  );
};

export default ProfileDialog;
