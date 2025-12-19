import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Paper,
  Alert,
  Typography,
  useTheme,
} from "@mui/material";
import { forgot } from "../services/authService";

const ForgotPassword = () => {
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
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setLoading(true);

    try {
      await forgot(username.trim());
      setSuccess("Please check your email to reset your password.");
    } catch (err) {
      setError("Can't find this account or something went wrong.");
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
        Enter your username and we’ll send you a reset link.
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

      <Box component="form" onSubmit={handleSubmit}>
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
          {loading ? "Sending..." : "Send reset link"}
        </Button>
      </Box>
    </Paper>
  );
};

export default ForgotPassword;
