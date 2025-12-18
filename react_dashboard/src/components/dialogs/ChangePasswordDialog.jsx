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
        slotProps={{
          paper: {
            sx: {
              borderRadius: 4,
              width: 380,
              background: "linear-gradient(180deg, #1e1e2f, #1a1a27)",
              boxShadow: "0 20px 50px rgba(0,0,0,0.45)",
              color: "white",
            },
          },
        }}
      >
        <DialogTitle>
          <Typography
            component="div"
            variant="h6"
            fontWeight="bold"
            color="white"
          >
            Change Password
          </Typography>
          <Typography
            component="div"
            variant="body2"
            color="rgba(255,255,255,0.65)"
          >
            Choose a strong password to protect your account
          </Typography>
        </DialogTitle>

        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            {error && <Alert severity="error">{error}</Alert>}

            {/* CURRENT */}
            <TextField
              label="Current Password"
              type={showCurrent ? "text" : "password"}
              fullWidth
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              InputLabelProps={{ style: { color: "#bdbdbd" } }}
              InputProps={{
                style: { color: "white" },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowCurrent((v) => !v)}
                      edge="end"
                      sx={{ color: "#bdbdbd" }}
                    >
                      {showCurrent ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 2,
                  "& fieldset": { borderColor: "#555" },
                  "&:hover fieldset": { borderColor: "#90caf9" },
                  "&.Mui-focused fieldset": { borderColor: "#90caf9" },
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
              InputLabelProps={{ style: { color: "#bdbdbd" } }}
              InputProps={{
                style: { color: "white" },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowNew((v) => !v)}
                      edge="end"
                      sx={{ color: "#bdbdbd" }}
                    >
                      {showNew ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 2,
                  "& fieldset": { borderColor: "#555" },
                  "&:hover fieldset": { borderColor: "#90caf9" },
                  "&.Mui-focused fieldset": { borderColor: "#90caf9" },
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
              InputLabelProps={{ style: { color: "#bdbdbd" } }}
              InputProps={{
                style: { color: "white" },
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowConfirm((v) => !v)}
                      edge="end"
                      sx={{ color: "#bdbdbd" }}
                    >
                      {showConfirm ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 2,
                  "& fieldset": { borderColor: "#555" },
                  "&:hover fieldset": { borderColor: "#90caf9" },
                  "&.Mui-focused fieldset": { borderColor: "#90caf9" },
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
                  color: "#e0e0e0",
                  borderColor: "#666",
                  "&:hover": {
                    borderColor: "#90caf9",
                    backgroundColor: "rgba(144,202,249,0.08)",
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
