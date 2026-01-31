import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
  LinearProgress,
  useTheme,
  Container,
  alpha,
  Stack,
  IconButton,
} from "@mui/material";
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { register } from "../services/authService";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

/* ================= Password Strength ================= */
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
/* ===================================================== */

const Register = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const pageBg = isDark
    ? "radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 100%)"
    : "radial-gradient(circle at 50% 0%, #e0f2fe 0%, #f8fafc 100%)";

  const cardBg = isDark
    ? alpha(theme.palette.background.paper, 0.4)
    : alpha("#ffffff", 0.6);

  const titleColor = isDark ? "white" : theme.palette.text.primary;
  const subtitleColor = isDark
    ? "rgba(255,255,255,0.7)"
    : theme.palette.text.secondary;
  const labelColor = isDark ? "#bdbdbd" : theme.palette.text.secondary;
  const inputColor = isDark ? "white" : theme.palette.text.primary;
  const borderColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)";
  const hoverBorder = isDark ? "#38bdf8" : "#6366f1";

  const [form, setForm] = useState({
    username: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const strength = getPasswordStrength(form.password);
  const strengthInfo = strengthLabel(strength);

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (form.password !== form.confirm_password) {
      setError("Password does not match");
      return;
    }

    if (strength < 3) {
      setError("Password is too weak");
      return;
    }

    try {
      setLoading(true);
      const res = await register({
        username: form.username.trim(),
        password: form.password,
      });

      if (res.data?.success === false) {
        setError(res.data.message || "User already exists");
        return;
      }

      setSuccess("Account created successfully!");
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError("Sign up failed!");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: pageBg,
        overflow: "hidden",
        position: "relative",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Return to Landing Page */}
      <IconButton
        component={Link}
        to="/"
        sx={{
          position: "absolute",
          top: 20,
          left: 20,
          zIndex: 10,
          color: isDark ? "white" : "text.primary",
          bgcolor: isDark ? "rgba(255,255,255,0.1)" : "rgba(255,255,255,0.6)",
          backdropFilter: "blur(10px)",
          "&:hover": {
            bgcolor: isDark ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.9)",
          },
        }}
      >
        <ArrowBackIcon />
      </IconButton>
      {/* Animated Background Shapes */}
      <Box
        component={motion.div}
        animate={{
          y: [0, -20, 0],
          rotate: [0, 5, 0],
        }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        sx={{
          position: "absolute",
          top: "10%",
          left: "20%",
          width: "30vw",
          height: "30vw",
          borderRadius: "50%",
          background: isDark
            ? "radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%)"
            : "radial-gradient(circle, rgba(56,189,248,0.25) 0%, transparent 70%)",
          filter: "blur(60px)",
          zIndex: 0,
        }}
      />
      <Box
        component={motion.div}
        animate={{
          y: [0, 30, 0],
          x: [0, -20, 0],
        }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 1 }}
        sx={{
          position: "absolute",
          bottom: "10%",
          right: "20%",
          width: "25vw",
          height: "25vw",
          borderRadius: "50%",
          background: isDark
            ? "radial-gradient(circle, rgba(168,85,247,0.12) 0%, transparent 70%)"
            : "radial-gradient(circle, rgba(168,85,247,0.2) 0%, transparent 70%)",
          filter: "blur(80px)",
          zIndex: 0,
        }}
      />

      <Container maxWidth="xs" sx={{ position: "relative", zIndex: 1 }}>
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <Paper
            elevation={0}
            sx={{
              p: { xs: 4, sm: 5 },
              borderRadius: 4,
              background: cardBg,
              backdropFilter: "blur(20px)",
              border: "1px solid",
              borderColor: borderColor,
              boxShadow: isDark
                ? "0 20px 50px rgba(0,0,0,0.4)"
                : "0 20px 50px rgba(0,0,0,0.1)",
            }}
          >
            <Box textAlign="center" mb={4}>
              <Typography
                variant="h3"
                fontWeight={800}
                color={titleColor}
                gutterBottom
                sx={{
                  background: isDark
                    ? "linear-gradient(to right, #ffffff, #94a3b8)"
                    : "linear-gradient(to right, #1e293b, #475569)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Create Account
              </Typography>
              <Typography variant="body2" color={subtitleColor}>
                Join us today and start your journey.
              </Typography>
            </Box>

            {error && (
              <Alert
                severity="error"
                sx={{
                  mb: 3,
                  borderRadius: 2,
                  bgcolor: isDark ? "rgba(211,47,47,0.1)" : "rgba(211,47,47,0.05)",
                  color: isDark ? "#ffcdd2" : "#d32f2f",
                }}
              >
                {error}
              </Alert>
            )}
            {success && (
              <Alert
                severity="success"
                sx={{
                  mb: 3,
                  borderRadius: 2,
                  bgcolor: isDark ? "rgba(46,125,50,0.1)" : "rgba(46,125,50,0.05)",
                  color: isDark ? "#a5d6a7" : "#388e3c",
                }}
              >
                {success}
              </Alert>
            )}

            <Box component="form" onSubmit={handleSubmit}>
              <TextField
                name="username"
                label="Username"
                fullWidth
                margin="normal"
                value={form.username}
                onChange={handleChange}
                required
                InputLabelProps={{ style: { color: labelColor } }}
                InputProps={{
                  style: { color: inputColor },
                  sx: {
                    borderRadius: 2,
                    bgcolor: isDark ? "rgba(0,0,0,0.2)" : "rgba(255,255,255,0.4)",
                    "& fieldset": { borderColor: borderColor },
                    "&:hover fieldset": { borderColor: hoverBorder },
                    "&.Mui-focused fieldset": { borderColor: hoverBorder },
                  },
                }}
              />

              <TextField
                name="password"
                label="Password"
                type="password"
                fullWidth
                margin="normal"
                value={form.password}
                onChange={handleChange}
                required
                InputLabelProps={{ style: { color: labelColor } }}
                InputProps={{
                  style: { color: inputColor },
                  sx: {
                    borderRadius: 2,
                    bgcolor: isDark ? "rgba(0,0,0,0.2)" : "rgba(255,255,255,0.4)",
                    "& fieldset": { borderColor: borderColor },
                    "&:hover fieldset": { borderColor: hoverBorder },
                    "&.Mui-focused fieldset": { borderColor: hoverBorder },
                  },
                }}
              />

              {form.password && (
                <Box mt={1} mb={2}>
                  <LinearProgress
                    variant="determinate"
                    value={(strength / 5) * 100}
                    color={strengthInfo.color}
                    sx={{ height: 6, borderRadius: 3, bgcolor: alpha("#000", 0.1) }}
                  />
                  <Typography
                    variant="caption"
                    sx={{ color: `${strengthInfo.color}.main`, mt: 0.5, display: "block", fontWeight: 600 }}
                  >
                    Strength: {strengthInfo.label}
                  </Typography>
                </Box>
              )}

              <TextField
                name="confirm_password"
                label="Confirm Password"
                type="password"
                fullWidth
                margin="normal"
                value={form.confirm_password}
                onChange={handleChange}
                required
                InputLabelProps={{ style: { color: labelColor } }}
                InputProps={{
                  style: { color: inputColor },
                  sx: {
                    borderRadius: 2,
                    bgcolor: isDark ? "rgba(0,0,0,0.2)" : "rgba(255,255,255,0.4)",
                    "& fieldset": { borderColor: borderColor },
                    "&:hover fieldset": { borderColor: hoverBorder },
                    "&.Mui-focused fieldset": { borderColor: hoverBorder },
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
                  py: 1.5,
                  fontWeight: 700,
                  fontSize: "1rem",
                  borderRadius: 3,
                  textTransform: "none",
                  background: "linear-gradient(90deg, #38bdf8, #6366f1)",
                  boxShadow: "0 10px 30px -10px rgba(99,102,241,0.5)",
                  "&:hover": {
                    background: "linear-gradient(90deg, #60a5fa, #7c3aed)",
                    transform: "translateY(-2px)",
                    boxShadow: "0 20px 40px -10px rgba(99,102,241,0.6)",
                  },
                  "&:disabled": {
                    background: "rgba(0,0,0,0.12)",
                    boxShadow: "none",
                  },
                }}
              >
                {loading ? "Creating account..." : "Register"}
              </Button>
            </Box>

            <Stack direction="row" spacing={1} justifyContent="center" mt={4}>
              <Typography variant="body2" color={subtitleColor}>
                Already have an account?
              </Typography>
              <Button
                component={Link}
                to="/login"
                variant="text"
                size="small"
                sx={{
                  padding: 0,
                  minWidth: "auto",
                  color: isDark ? "#38bdf8" : "#6366f1",
                  textTransform: "none",
                  fontWeight: 600,
                  "&:hover": {
                    backgroundColor: "transparent",
                    textDecoration: "underline",
                  },
                }}
              >
                Login
              </Button>
            </Stack>

            <Box mt={2} textAlign="center">
              <Typography variant="caption" color="text.secondary" sx={{ opacity: 0.7 }}>
                © {new Date().getFullYear()} FMC
              </Typography>
            </Box>
          </Paper>
        </motion.div>
      </Container>
    </Box>
  );
};

export default Register;
