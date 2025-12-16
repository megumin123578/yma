import { useState } from "react";
import {
  Box,
  Button,
  TextField,
  Typography,
  Paper,
  Alert,
} from "@mui/material";
import { forgotPasswordApi } from "../api/authApi";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    await forgotPasswordApi(email);
    setSuccess("Vui lòng kiểm tra email để reset mật khẩu");
  };

  return (
    <Box display="flex" justifyContent="center" alignItems="center" height="100%">
      <Paper elevation={3} sx={{ p: 4, width: 360 }}>
        <Typography variant="h5" mb={2} textAlign="center">
          Forgot Password
        </Typography>

        {success && <Alert severity="success">{success}</Alert>}

        <Box component="form" onSubmit={handleSubmit}>
          <TextField
            label="Email"
            fullWidth
            margin="normal"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>
            Send reset link
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default ForgotPassword;
