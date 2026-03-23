import {
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  Snackbar,
  LinearProgress,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { useState, useMemo } from "react";
import { changePassword } from "../../services/authService";

import InputAdornment from "@mui/material/InputAdornment";
import IconButton from "@mui/material/IconButton";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";



const getPasswordStrength = (password) => {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return score;
};

const strengthMap = [
  { label: "Very weak", color: "error" },
  { label: "Weak", color: "error" },
  { label: "Fair", color: "warning" },
  { label: "Good", color: "info" },
  { label: "Strong", color: "success" },
];

const ChangePasswordDialog = ({ open, onClose }) => {

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

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const [ showCurrent, setShowCurrent ] = useState(false)
  const [ showNew, setShowNew ] = useState(false)
  const [ showConfirm, setShowConfirm ] = useState(false)

  const strength = useMemo(
    () => getPasswordStrength(next),
    [next]
  );

  const resetForm = () => {
    setCurrent("");
    setNext("");
    setConfirm("");
    setError("");
    setSuccess(false);
  };

  const handleSubmit = async () => {
    setError("");

    if (!current || !next || !confirm) {
      setError("Please fill in all fields");
      return;
    }

    if (next !== confirm) {
      setError("Passwords do not match");
      return;
    }

    if (strength < 2) {
      setError("Password is too weak");
      return;
    }

    try {
      setLoading(true);
      await changePassword(current, next);
      setSuccess(true);

      setTimeout(() => {
        resetForm();
        onClose();
      }, 800);
    } catch (err) {
      setError(err.message || "Change password failed");
    } finally {
      setLoading(false);
    }
  };

  const strengthInfo = strengthMap[strength];

  return (
    <>
      <Dialog
        open={open}
        onClose={() => {
          resetForm();
          onClose();
        }}
        fullScreen={isMobile}
        slotProps={{
          paper: {
            sx: {
              width: { xs: "100vw", sm: 380 },
              maxWidth: { xs: "100vw", sm: 380 },
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
        <DialogTitle>
          <Typography
            component="div"
            variant="h6"
            fontWeight="bold"
            color={titleColor}
          >
            Change Password
          </Typography>
          <Typography
            component="div"
            variant="body2"
            color={subtitleColor}
          >
            Submit a password change request. The new password is applied only after admin approval.
          </Typography>
        </DialogTitle>

        <DialogContent sx={{ px: { xs: 2, sm: 3 } }}>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            {error && <Alert severity="error">{error}</Alert>}
            {success && (
              <Alert severity="success">
                Password change request submitted. Wait for admin approval.
              </Alert>
            )}

            {/* CURRENT */}
            <TextField
              label="Current Password"
              type={showCurrent ? "text" : "password"}
              fullWidth
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              InputLabelProps={{ style: { color: labelColor } }}
              InputProps={{
                style: { color: inputColor },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowCurrent((v) => !v)}
                      edge="end"
                      sx={{ color: labelColor }}
                    >
                      {showCurrent ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
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


            {/* NEW */}
            <TextField
              label="New Password"
              type={showNew ? "text" : "password"}
              fullWidth
              value={next}
              onChange={(e) => setNext(e.target.value)}
              InputLabelProps={{ style: { color: labelColor } }}
              InputProps={{
                style: { color: inputColor },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowNew((v) => !v)}
                      edge="end"
                      sx={{ color: labelColor }}
                    >
                      {showNew ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
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
            {/* STRENGTH */}
            {next && (
              <Box>
                <LinearProgress
                  variant="determinate"
                  value={(strength / 4) * 100}
                  color={strengthInfo.color}
                  sx={{ height: 6, borderRadius: 3, mb: 0.5 }}
                />
                <Typography
                  variant="caption"
                  color={`${strengthInfo.color}.main`}
                >
                  Strength: {strengthInfo.label}
                </Typography>
              </Box>
            )}

            {/* CONFIRM */}
            <TextField
              label="Confirm New Password"
              type={showConfirm ? "text" : "password"}
              fullWidth
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              InputLabelProps={{ style: { color: labelColor } }}
              InputProps={{
                style: { color: inputColor },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowConfirm((v) => !v)}
                      edge="end"
                      sx={{ color: labelColor }}
                    >
                      {showConfirm ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
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
            <Box display="flex" gap={1} mt={1}>
              <Button
                fullWidth
                variant="outlined"
                onClick={() => {
                  resetForm();
                  onClose();
                }}
                disabled={loading}
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
                onClick={handleSubmit}
                disabled={loading || success}
                sx={{
                  fontWeight: 600,
                  background:
                    "linear-gradient(90deg, #42a5f5, #478ed1)",
                  "&:hover": {
                    background:
                      "linear-gradient(90deg, #64b5f6, #5e92f3)",
                    boxShadow:
                      "0 10px 25px rgba(66,165,245,0.4)",
                  },
                }}
              >
                {loading ? "Saving..." : "Save"}
              </Button>
            </Box>
          </Box>
        </DialogContent>
      </Dialog>

      {/* SUCCESS */}
      <Snackbar
        open={success}
        autoHideDuration={2000}
        onClose={() => setSuccess(false)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity="success" variant="filled">
          Password changed successfully
        </Alert>
      </Snackbar>
    </>
  );
};

export default ChangePasswordDialog;
