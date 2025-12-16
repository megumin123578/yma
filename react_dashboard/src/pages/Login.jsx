import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Paper,
  Alert,
  Typography,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/authService";

const Login = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await login(username.trim(), password);
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
        background: "linear-gradient(180deg, #1e1e2f, #1a1a27)",
        boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
        animation: "fadeInUp 0.6s ease",
        "@keyframes fadeInUp": {
          from: { opacity: 0, transform: "translateY(30px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        transition: "all 0.3s ease",
        "&:hover": {
          transform: "translateY(-4px)",
          boxShadow: "0 28px 70px rgba(0,0,0,0.45)",
        },
      }}
    >
      <Typography variant="h5" fontWeight="bold" mb={1} color="white">
        Login
      </Typography>

      <Typography
        variant="body2"
        mb={3}
        color="rgba(255,255,255,0.7)"
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
          InputLabelProps={{ style: { color: "#bdbdbd" } }}
          InputProps={{ style: { color: "white" } }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              "& fieldset": { borderColor: "#555" },
              "&:hover fieldset": { borderColor: "#90caf9" },
              "&.Mui-focused fieldset": { borderColor: "#90caf9" },
            },
          }}
        />

        {/* Password */}
        <TextField
          label="Password"
          type="password"
          fullWidth
          margin="normal"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          InputLabelProps={{ style: { color: "#bdbdbd" } }}
          InputProps={{ style: { color: "white" } }}
          sx={{
            "& .MuiOutlinedInput-root": {
              borderRadius: 2,
              "& fieldset": { borderColor: "#555" },
              "&:hover fieldset": { borderColor: "#90caf9" },
              "&.Mui-focused fieldset": { borderColor: "#90caf9" },
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
        <Typography variant="body2" color="rgba(255,255,255,0.7)">
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
    </Paper>
  );
};

export default Login;
