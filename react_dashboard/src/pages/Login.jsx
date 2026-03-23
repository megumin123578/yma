import { useState, useContext } from "react";
import { UserContext } from "../context/UserContext";
import { getMe } from "../services/userService";

import {
  Box,
  Button,
  TextField,
  Paper,
  Alert,
  Typography,
  useTheme,
  IconButton,
  InputAdornment,
  Container,
  alpha,
  Stack,
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/authService";
import { motion } from "framer-motion";

const Login = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  // Modern background matching Landing Page
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

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { setUser } = useContext(UserContext);

  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      await login(username.trim(), password);
      const me = await getMe();
      setUser(me);

      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError("Username or password is incorrect.");
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
                Welcome Back
              </Typography>
              <Typography variant="body2" color={subtitleColor}>
                Enter your credentials to access your account.
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
                label="Password"
                type={showPassword ? "text" : "password"}
                fullWidth
                margin="normal"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                InputLabelProps={{ style: { color: labelColor } }}
                InputProps={{
                  style: { color: inputColor },
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword((prev) => !prev)}
                        edge="end"
                        sx={{ color: labelColor }}
                      >
                        {showPassword ? (
                          <VisibilityOffOutlinedIcon fontSize="small" />
                        ) : (
                          <VisibilityOutlinedIcon fontSize="small" />
                        )}
                      </IconButton>
                    </InputAdornment>
                  ),
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
                {loading ? "Logging in..." : "Login"}
              </Button>
            </Box>

            <Stack direction="row" spacing={1} justifyContent="center" mt={4}>
              <Typography variant="body2" color={subtitleColor}>
                Don’t have an account?
              </Typography>
              <Button
                component={Link}
                to="/register"
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
                Sign Up
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

export default Login;
