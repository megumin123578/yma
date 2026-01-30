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
} from "@mui/material";
import { register } from "../services/authService";
import { Link, useNavigate } from "react-router-dom";

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
        Create Account
      </Typography>

      <Typography
        variant="body2"
        mb={3}
        color={subtitleColor}
      >
        Fill in the information below to create a new account.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Box component="form" onSubmit={handleSubmit}>
        {/* Username */}
        <TextField
          name="username"
          label="Username"
          fullWidth
          margin="normal"
          value={form.username}
          onChange={handleChange}
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
          name="password"
          label="Password"
          type="password"
          fullWidth
          margin="normal"
          value={form.password}
          onChange={handleChange}
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

        {/* Password strength */}
        {form.password && (
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

        {/* Confirm password */}
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
          {loading ? "Creating account..." : "Register"}
        </Button>

        {/* Back to login */}
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
          onClick={() => navigate("/login")}
        >
          Back to Login
        </Button>
      </Box>
      <Box mt={2} textAlign="center">
        <Typography variant="caption" color={subtitleColor}>
          By creating an account, you agree to our
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

export default Register;
