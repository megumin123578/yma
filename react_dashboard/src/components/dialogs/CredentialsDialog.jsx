import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Divider,
  useTheme,
} from "@mui/material";
import { useEffect, useState } from "react";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { uploadCredentials, listTokens, deleteToken } from "../../services/userService";

const CredentialsDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const [file, setFile] = useState(null);
  const [filename, setFilename] = useState("");
  const [status, setStatus] = useState({ type: "", message: "" });
  const [uploading, setUploading] = useState(false);
  const [authUrl, setAuthUrl] = useState("");
  const [tokens, setTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);

  useEffect(() => {
    if (open) {
      setFile(null);
      setFilename("");
      setStatus({ type: "", message: "" });
      setUploading(false);
      setAuthUrl("");
      loadTokens();
    }
  }, [open]);

  const loadTokens = async () => {
    setLoadingTokens(true);
    try {
      const data = await listTokens();
      setTokens(data?.tokens || []);
    } catch (err) {
      setTokens([]);
    } finally {
      setLoadingTokens(false);
    }
  };

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

  const handleDeleteToken = async (tokenName) => {
    try {
      await deleteToken(tokenName);
      await loadTokens();
    } catch (err) {
      const message =
        err?.response?.data?.detail || "Delete failed. Please try again.";
      setStatus({ type: "error", message });
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

          <Divider />

          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography variant="subtitle2">Tokens</Typography>
            <Button size="small" onClick={loadTokens} disabled={loadingTokens}>
              {loadingTokens ? "Refreshing..." : "Refresh"}
            </Button>
          </Box>

          {tokens.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              {loadingTokens ? "Loading tokens..." : "No tokens found."}
            </Typography>
          ) : (
            <Box display="flex" flexDirection="column" gap={1}>
              {tokens.map((name) => {
                const displayName = name.toLowerCase().endsWith(".pickle")
                  ? name.slice(0, -7)
                  : name;
                return (
                <Box
                  key={name}
                  display="flex"
                  alignItems="center"
                  justifyContent="space-between"
                  sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 1, p: 1 }}
                >
                  <Typography variant="body2">{displayName}</Typography>
                  <Button
                    size="small"
                    color="error"
                    onClick={() => handleDeleteToken(name)}
                  >
                    Delete
                  </Button>
                </Box>
              )})}
            </Box>
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
