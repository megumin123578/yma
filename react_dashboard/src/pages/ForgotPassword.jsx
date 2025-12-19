import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Paper,
  Alert,
  Typography,
  LinearProgress,
  useTheme,
} from "@mui/material";
import { resetPassword } from "../services/authService";
import { useNavigate } from "react-router-dom";

const getPasswordStrength = (password) => {
  let score = 0;
  if (password.length >= 8) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  return score;
};

const strengthLabel = (score) => {
  switch (score) {
    case 1:
    case 2:
      return { label: "Weak", color: "error" };
    case 3:
      return { label: "Medium", color: "warning" };
    case 4:
    case 5:
      return { label: "Strong", color: "success" };
    default:
      return { label: "", color: "inherit" };
  }
};

const ForgotPassword = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const paperBg = isDark
    ? "linear-gradient(180deg, #1e1e2f, #1a1a27)"
    : theme.palette.background.paper;
  const paperShadow = isDark
    ? "0 20px 50px rgba(0,0,0,0.35)"
    : "0 14px 40px rgba(0,0,0,0.15)";
  const titleColor = isDark ? "white" : theme.palette.text.primary;
  const subtitleColor = isDark
    ? "rgba(255,255,255,0.7)"
    : theme.palette.text.secondary;
  const labelColor = isDark ? "#bdbdbd" : theme.palette.text.secondary;
  const inputColor = isDark ? "white" : theme.palette.text.primary;
  const borderColor = isDark ? "#555" : "#d0d0d0";
  const hoverBorder = isDark ? "#90caf9" : theme.palette.primary.main;

  const [username, setUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const strength = getPasswordStrength(newPassword);
  const strengthInfo = strengthLabel(strength);

  const handleReset = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!username || !newPassword || !confirm) {
      setError("Please fill in all fields");
      return;
    }

    if (newPassword !== confirm) {
      setError("Passwords do not match");
      return;
    }

    if (strength < 3) {
      setError("Password is too weak");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(username.trim(), newPassword);
      setSuccess("Password reset successfully. You can login now.");
      setTimeout(() => navigate("/"), 1200);
    } catch (err) {
      setError("Username not found or reset failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        p: 5,
        width: 520,
        borderRadius: 4,
        background: paperBg,
        boxShadow: paperShadow,
        animation: "fadeInUp 0.6s ease",
        "@keyframes fadeInUp": {
          from: { opacity: 0, transform: "translateY(30px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        transition: "all 0.3s ease",
        "&:hover": {
          transform: "translateY(-4px)",
          boxShadow: isDark
            ? "0 28px 70px rgba(0,0,0,0.45)"
            : "0 18px 40px rgba(0,0,0,0.12)",
        },
      }}
    >
      <Typography
        variant="h5"
        fontWeight="bold"
        mb={1}
        color={titleColor}
      >
        Forgot Password
      </Typography>

      <Typography
        variant="body2"
        mb={3}
        color={subtitleColor}
      >
        Enter your username and a new password to reset.
      </Typography>

      {success && (
        <Alert severity="success" sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box component="form" onSubmit={handleReset}>
        <TextField
          label="Username"
          fullWidth
          margin="normal"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          InputLabelProps={{ style: { color: labelColor } }}
          InputProps={{
            style: { color: inputColor },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              "& fieldset": {
                borderColor,
              },
              "&:hover fieldset": {
                borderColor: hoverBorder,
              },
              "&.Mui-focused fieldset": {
                borderColor: hoverBorder,
              },
            },
          }}
        />

        <TextField
          label="New Password"
          type="password"
          fullWidth
          margin="normal"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
          InputLabelProps={{ style: { color: labelColor } }}
          InputProps={{
            style: { color: inputColor },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              "& fieldset": {
                borderColor,
              },
              "&:hover fieldset": {
                borderColor: hoverBorder,
              },
              "&.Mui-focused fieldset": {
                borderColor: hoverBorder,
              },
            },
          }}
        />

        {newPassword && (
          <Box mt={1}>
            <LinearProgress
              variant="determinate"
              value={(strength / 5) * 100}
              color={strengthInfo.color}
              sx={{ height: 8, borderRadius: 4 }}
            />
            <Typography
              variant="caption"
              color={`${strengthInfo.color}.main`}
            >
              {strengthInfo.label}
            </Typography>
          </Box>
        )}

        <TextField
          label="Confirm New Password"
          type="password"
          fullWidth
          margin="normal"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          InputLabelProps={{ style: { color: labelColor } }}
          InputProps={{
            style: { color: inputColor },
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              "& fieldset": {
                borderColor,
              },
              "&:hover fieldset": {
                borderColor: hoverBorder,
              },
              "&.Mui-focused fieldset": {
                borderColor: hoverBorder,
              },
            },
          }}
        />

        <Button
          type="submit"
          variant="contained"
          fullWidth
          disabled={loading}
          sx={{
            mt: 3,
            py: 1.4,
            fontWeight: 600,
            borderRadius: 2,
            background: "linear-gradient(90deg, #42a5f5, #478ed1)",
            transition: "all 0.3s ease",
            "&:hover": {
              background: "linear-gradient(90deg, #64b5f6, #5e92f3)",
              transform: "translateY(-2px)",
              boxShadow: "0 10px 25px rgba(66,165,245,0.4)",
            },
            "&:active": {
              transform: "translateY(0)",
            },
          }}
        >
          {loading ? "Resetting..." : "Reset Password"}
        </Button>

        <Button
          variant="text"
          fullWidth
          sx={{
            mt: 1,
            color: "#90caf9",
            textTransform: "none",
            "&:hover": {
              backgroundColor: "transparent",
              textDecoration: "underline",
            },
          }}
          onClick={() => navigate("/")}
        >
          Back to Login
        </Button>
      </Box>
    </Paper>
  );
};

export default ForgotPassword;
