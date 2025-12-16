import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
  LinearProgress,
} from "@mui/material";
import { register } from "../services/authService";
import { useNavigate } from "react-router-dom";



const getPasswordStrength = (password) => {
  let score = 0;

  if (password.length >= 8) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  return score; // 0 - 5
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

const Register = () => {
  const [form, setForm] = useState({
    username: "",
    password: "",
    confirm_password: "",
  });
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const strength = getPasswordStrength(form.password);
  const strengthInfo = strengthLabel(strength);

  const navigate = useNavigate();

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (form.password !== form.confirm_password) {
      setError("Passwords do not match");
      return;
    }

    if (strength < 3) {
      setError("Password is too weak");
      return;
    }

    try {
      setLoading(true);

      const res = await register({
        username: form.username,
        password: form.password,
      });

      // ĐỌC RESPONSE
      if (res.data.success === false) {
        setError(res.data.message); // User existed
        return;
      }

      setSuccess(res.data.message || "Sign up successfully!");
      setTimeout(() => {
        navigate("/");
      }, 1500);
    } catch (err) {
      setError("Sign up failed!");
    } finally {
      setLoading(false);
    }
  };


  return (
    <Box
      minHeight="100vh"
      display="flex"
      justifyContent="center"
      alignItems="center"
      bgcolor="background.default"
    >
      <Paper
        elevation={4}
        sx={{
            p: 5,
            width: "100%",
            maxWidth: 480,
        }}
        >
        <Typography variant="h5" fontWeight="bold" textAlign="center">
          Create Account
        </Typography>

        <Typography
          variant="body2"
          color="text.secondary"
          mb={2}
          textAlign="center"
        >
          Fill in the information below
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            name="username"
            label="Username"
            fullWidth
            margin="normal"
            value={form.username}
            onChange={handleChange}
            required
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
          />

          {/* Password strength bar */}
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

          <TextField
            name="confirm_password"
            label="Confirm Password"
            type="password"
            fullWidth
            margin="normal"
            value={form.confirm_password}
            onChange={handleChange}
            required
          />

          <Button
            type="submit"
            variant="contained"
            fullWidth
            sx={{ mt: 3, py: 1.2 }}
            disabled={loading}
          >
            {loading ? "Creating account..." : "Register"}
          </Button>
          <Button
          variant="text"
          fullWidth
          sx={{
            mt: 1,
            color: "white",
            transition: "all 0.2s ease",
            "&:hover": {
              color: "#90caf9",
              backgroundColor: "rgba(255,255,255,0.08)",
            },
          }}
          onClick={() => navigate("/")}
        >
          Back to Login page
        </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default Register;
