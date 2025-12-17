import {
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  Button,
  Box,
  Typography,
  Alert,
  Snackbar,
  useTheme,
} from "@mui/material";
import { useState } from "react";
import { changePassword } from "../../services/authService";

const ChangePasswordDialog = ({ open, onClose }) => {
  const theme = useTheme();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const resetForm = () => {
    setCurrent("");
    setNext("");
    setConfirm("");
    setError("");
    setSuccess(false);
  };

  const handleSubmit = async () => {
    setError("");

    if (!current || !next || !confirm) {
      setError("Please fill in all fields");
      return;
    }

    if (next !== confirm) {
      setError("Passwords do not match");
      return;
    }

    try {
      setLoading(true);
      await changePassword(current, next);
      setSuccess(true);

      // đóng dialog nhẹ nhàng sau khi success
      setTimeout(() => {
        resetForm();
        onClose();
      }, 800);
    } catch (err) {
      setError(err.message || "Change password failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={() => {
          resetForm();
          onClose();
        }}
        slotProps={{
          paper: {
            sx: {
              borderRadius: 3,
              width: 360,
              backgroundColor: theme.palette.background.paper,
            },
          },
        }}
      >
        <DialogTitle>
          <Typography fontWeight="bold">
            Change Password
          </Typography>
        </DialogTitle>

        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} mt={1}>
            {error && <Alert severity="error">{error}</Alert>}

            <TextField
              label="Current Password"
              type="password"
              fullWidth
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />

            <TextField
              label="New Password"
              type="password"
              fullWidth
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />

            <TextField
              label="Confirm New Password"
              type="password"
              fullWidth
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />

            <Box display="flex" gap={1} mt={1}>
              <Button
                fullWidth
                variant="outlined"
                onClick={() => {
                  resetForm();
                  onClose();
                }}
                disabled={loading}
              >
                Cancel
              </Button>

              <Button
                fullWidth
                variant="contained"
                onClick={handleSubmit}
                disabled={loading || success}
              >
                {loading ? "Saving..." : "Save"}
              </Button>
            </Box>
          </Box>
        </DialogContent>
      </Dialog>

      {/* SUCCESS POPUP */}
      <Snackbar
        open={success}
        autoHideDuration={2000}
        onClose={() => setSuccess(false)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity="success" variant="filled">
          Password changed successfully
        </Alert>
      </Snackbar>
    </>
  );
};

export default ChangePasswordDialog;
