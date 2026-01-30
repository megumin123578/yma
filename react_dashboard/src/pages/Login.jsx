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
} from "@mui/material";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import VisibilityOffOutlinedIcon from "@mui/icons-material/VisibilityOffOutlined";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/authService";

const Login = () => {
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
      <Typography variant="h5" fontWeight="bold" mb={1} color={titleColor}>
        Login
      </Typography>

      <Typography
        variant="body2"
        mb={3}
        color={subtitleColor}
      >
        Enter your credentials to access your account.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box component="form" onSubmit={handleSubmit}>
        {/* Username */}
        <TextField
          label="Username"
          fullWidth
          margin="normal"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          InputLabelProps={{ style: { color: labelColor } }}
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

        {/* Password */}
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
                  aria-label={showPassword ? "Hide password" : "Show password"}
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

        {/* Forgot password */}
        <Box textAlign="right" mt={1}>
          <Button
            component={Link}
            to="/forgot-password"
            variant="text"
            sx={{
              color: "#90caf9",
              textTransform: "none",
              "&:hover": {
                backgroundColor: "transparent",
                textDecoration: "underline",
              },
            }}
          >
            Forgot password?
          </Button>
        </Box>

        {/* Submit */}
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
            "&:active": { transform: "translateY(0)" },
          }}
        >
          {loading ? "Logging in..." : "Login"}
        </Button>
      </Box>

      {/* Register */}
      <Box mt={3} textAlign="center">
        <Typography variant="body2" color={subtitleColor}>
          Don’t have an account?
          <Button
            component={Link}
            to="/register"
            variant="text"
            sx={{
              ml: 1,
              color: "#90caf9",
              textTransform: "none",
              fontWeight: 500,
              "&:hover": {
                backgroundColor: "transparent",
                textDecoration: "underline",
              },
            }}
          >
            Register
          </Button>
        </Typography>
      </Box>
      <Box mt={2} textAlign="center">
        <Typography variant="caption" color={subtitleColor}>
          By using this app, you agree to our
          <Button
            component={Link}
            to="/terms"
            variant="text"
            sx={{
              ml: 0.5,
              color: "#90caf9",
              textTransform: "none",
              fontSize: "0.75rem",
              "&:hover": {
                backgroundColor: "transparent",
                textDecoration: "underline",
              },
            }}
          >
            Terms
          </Button>
          and
          <Button
            component={Link}
            to="/privacy"
            variant="text"
            sx={{
              ml: 0.5,
              color: "#90caf9",
              textTransform: "none",
              fontSize: "0.75rem",
              "&:hover": {
                backgroundColor: "transparent",
                textDecoration: "underline",
              },
            }}
          >
            Privacy Policy
          </Button>
          .
        </Typography>
      </Box>
    </Paper>
  );
};

export default Login;
