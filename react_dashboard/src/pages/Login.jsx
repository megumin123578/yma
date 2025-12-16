import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
} from "@mui/material";
import { Link } from "react-router-dom";
import { login } from "../services/authService";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(email, password);
      alert("Login success!");
      // navigate("/dashboard");
    } catch (err) {
      setError("Email hoặc mật khẩu không đúng");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box display="flex" justifyContent="center" alignItems="center" height="100%">
      <Paper elevation={3} sx={{ p: 4, width: 360 }}>
        <Typography variant="h5" fontWeight="bold" mb={2} textAlign="center">
          Login
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

        {/* FORM */}
        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            label="Email"
            fullWidth
            margin="normal"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <TextField
            label="Password"
            type="password"
            fullWidth
            margin="normal"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          {/* Forgot password */}
          <Box textAlign="right" mt={1}>
            <Button
              variant="text"
              size="small"
              component={Link}
              to="/forgot-password"
              sx={{
                color: "#1976d2",
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

          {/* Login */}
          <Button
            type="submit"
            variant="contained"
            fullWidth
            sx={{ mt: 2 }}
            disabled={loading}
          >
            {loading ? "Logging in..." : "Login"}
          </Button>
        </Box>

        {/* Register */}
        <Box mt={3} textAlign="center">
          <Typography variant="body2">
            Don’t have an account?
            <Button
              variant="text"
              size="small"
              component={Link}
              to="/register"
              sx={{
                ml: 1,
                color: "#1976d2",
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
      </Paper>
    </Box>
  );
};

export default Login;
