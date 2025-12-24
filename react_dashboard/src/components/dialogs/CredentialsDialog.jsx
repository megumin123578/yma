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
  Fade,
  useTheme,
} from "@mui/material";
import { useEffect, useState } from "react";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import RefreshIcon from "@mui/icons-material/Refresh";
import { uploadCredentials, listTokens, deleteToken } from "../../services/userService";

const CredentialsDialog = ({ open, onClose }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const surface = isDark ? "#14171c" : "#ffffff";
  const panel = isDark ? "#1b2027" : "#f6f7f9";
  const border = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const accent = isDark ? "#6dd6c6" : theme.palette.primary.main;
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
    const base = selected.name.toLowerCase().endsWith(".json")
      ? selected.name.slice(0, -5)
      : selected.name;
    setFilename(base);
  };

  const handleFilenameChange = (event) => {
    const raw = event.target.value || "";
    setFilename(raw.toLowerCase().endsWith(".json") ? raw.slice(0, -5) : raw);
  };

  const handleUpload = async () => {
    if (!file || uploading) return;

    setUploading(true);
    setStatus({ type: "", message: "" });

    try {
      const safeName = filename.trim() ? `${filename.trim()}.json` : "";
      const data = await uploadCredentials(file, safeName);
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
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      TransitionComponent={Fade}
      transitionDuration={220}
      PaperProps={{
        sx: {
          bgcolor: surface,
          color: isDark ? "#e9edf2" : "inherit",
          border: `1px solid ${border}`,
          boxShadow: isDark ? "0 18px 60px rgba(0,0,0,0.55)" : undefined,
          overflow: "hidden",
          position: "relative",
          "&:before": {
            content: '""',
            position: "absolute",
            inset: 0,
            background: isDark
              ? "radial-gradient(600px 300px at 110% -10%, rgba(109,214,198,0.16), transparent 55%)"
              : "radial-gradient(600px 300px at 110% -10%, rgba(25,118,210,0.08), transparent 55%)",
            pointerEvents: "none",
          },
        },
      }}
    >
      <DialogTitle sx={{ pb: 1, position: "relative", zIndex: 1 }}>
        <Box display="flex" flexDirection="column" gap={0.5}>
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            Add Channel
          </Typography>
          <Typography variant="body2" sx={{ color: isDark ? "#aab4c2" : "text.secondary" }}>
            Upload credentials, then authorize in your preferred browser profile.
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ position: "relative", zIndex: 1 }}>
        <Box display="flex" flexDirection="column" gap={2} mt={1}>
          <Box
            sx={{
              bgcolor: panel,
              border: `1px solid ${border}`,
              borderRadius: 2,
              p: 2,
              display: "flex",
              flexDirection: "column",
              gap: 1.5,
              transition: "transform 200ms ease, box-shadow 200ms ease",
              boxShadow: isDark ? "0 10px 24px rgba(0,0,0,0.35)" : "0 10px 24px rgba(0,0,0,0.08)",
              "&:hover": {
                transform: "translateY(-2px)",
              },
            }}
          >
            <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
              Upload credentials
            </Typography>

            <Button
              variant="outlined"
              component="label"
              startIcon={<UploadFileIcon />}
              sx={{
                borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                color: isDark ? "#e9edf2" : undefined,
                transition: "all 180ms ease",
                "&:hover": {
                  borderColor: isDark ? "rgba(255,255,255,0.4)" : undefined,
                  backgroundColor: isDark ? "rgba(255,255,255,0.06)" : undefined,
                  transform: "translateY(-1px)",
                },
              }}
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
              onChange={handleFilenameChange}
              placeholder="example.json"
              InputLabelProps={{ style: { color: isDark ? "#aab4c2" : undefined } }}
              sx={{
                input: { color: isDark ? "#e9edf2" : undefined },
                "& .MuiOutlinedInput-notchedOutline": {
                  borderColor: isDark ? "rgba(255,255,255,0.2)" : undefined,
                },
              }}
            />
          </Box>

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
              sx={{
                bgcolor: isDark ? "#2b8a7b" : undefined,
                transition: "transform 180ms ease",
                "&:hover": {
                  bgcolor: isDark ? "#247468" : undefined,
                  transform: "translateY(-1px)",
                },
              }}
            >
              Open Authorization Link
            </Button>
          )}

          <Divider />

          <Box
            sx={{
              bgcolor: panel,
              border: `1px solid ${border}`,
              borderRadius: 2,
              p: 2,
              display: "flex",
              flexDirection: "column",
              gap: 1.5,
              transition: "transform 200ms ease, box-shadow 200ms ease",
              boxShadow: isDark ? "0 10px 24px rgba(0,0,0,0.35)" : "0 10px 24px rgba(0,0,0,0.08)",
              "&:hover": {
                transform: "translateY(-2px)",
              },
            }}
          >
            <Box display="flex" alignItems="center" justifyContent="space-between">
              <Typography variant="subtitle2" sx={{ color: accent, letterSpacing: 0.3 }}>
                Tokens
              </Typography>
              <Button
                size="small"
                onClick={loadTokens}
                disabled={loadingTokens}
                sx={{
                  minWidth: 0,
                  color: isDark ? "#9fe3d6" : undefined,
                }}
              >
                <RefreshIcon fontSize="small" />
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
                      sx={{
                        border: `1px solid ${border}`,
                        borderRadius: 1,
                        p: 1,
                        bgcolor: isDark ? "rgba(255,255,255,0.02)" : "#ffffff",
                        transition: "all 180ms ease",
                        "&:hover": {
                          bgcolor: isDark ? "rgba(255,255,255,0.06)" : "rgba(25,118,210,0.04)",
                          borderColor: isDark ? "rgba(255,255,255,0.2)" : "rgba(25,118,210,0.2)",
                        },
                      }}
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
                  );
                })}
              </Box>
            )}
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button
          onClick={onClose}
          disabled={uploading}
          sx={{ color: isDark ? "#aab4c2" : "text.secondary" }}
        >
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
