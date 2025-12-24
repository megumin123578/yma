import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  useTheme,
} from "@mui/material";
import { useEffect, useState } from "react";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { uploadCredentials } from "../../services/userService";

const CredentialsDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const [file, setFile] = useState(null);
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);
  const [authUrl, setAuthUrl] = useState("");

  useEffect(() => {
    if (open) {
      setFile(null);
      setFilename("");
      setStatus({ type: "", message: "" });
      setUploading(false);
      setAuthUrl("");
    }
  }, [open]);

  const handleSelectFile = (event) => {
    const selected = event.target.files?.[0];
    if (!selected) return;

    if (!selected.name.toLowerCase().endsWith(".json")) {
      setStatus({
        type: "error",
        message: "Please select a .json credentials file.",
      });
      setFile(null);
      setFilename("");
      return;
    }

    setStatus({ type: "", message: "" });
    setFile(selected);
    setFilename(selected.name);
  };

  const handleUpload = async () => {
    if (!file || uploading) return;

    setUploading(true);
    setStatus({ type: "", message: "" });

    try {
      const data = await uploadCredentials(file, filename);
      const nextUrl = data?.auth_url || "";
      setAuthUrl(nextUrl);
      setStatus({
        type: "success",
        message: nextUrl
          ? "Credentials uploaded. Click the link to authorize."
          : "Credentials uploaded successfully.",
      });
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Upload failed. Please try again.";
      setStatus({ type: "error", message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Add Channel</DialogTitle>
      <DialogContent>
        <Box display="flex" flexDirection="column" gap={2} mt={1}>
          <Typography variant="body2" color="text.secondary">
            Upload a Google OAuth JSON credentials file.
          </Typography>

          <Button
            variant="outlined"
            component="label"
            startIcon={<UploadFileIcon />}
          >
            {file ? file.name : "Choose Credentials file"}
            <input
              hidden
              type="file"
              accept=".json,application/json"
              onChange={handleSelectFile}
            />
          </Button>

          <TextField
            label="File name"
            size="small"
            value={filename}
            onChange={(event) => setFilename(event.target.value)}
            placeholder="example.json"
          />

          {status.message && (
            <Typography
              variant="body2"
              color={
                status.type === "error"
                  ? theme.palette.error.main
                  : theme.palette.success.main
              }
            >
              {status.message}
            </Typography>
          )}

          {authUrl && (
            <Button
              variant="contained"
              color="success"
              href={authUrl}
              target="_blank"
              rel="noopener"
            >
              Open Authorization Link
            </Button>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={uploading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? "Uploading..." : "Upload"}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default CredentialsDialog;
