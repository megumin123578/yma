import { useMemo } from "react";
import {
  Alert,
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import EastRoundedIcon from "@mui/icons-material/EastRounded";

const formatDateTime = (value) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
};

const MailMessageDialog = ({ open, onClose, loading = false, error = "", message = null }) => {
  const messagePayload =
    message?.payload && typeof message.payload === "object"
      ? message.payload
      : {};
  const messageBody =
    messagePayload.text_body ||
    messagePayload.textBody ||
    message?.snippet ||
    "";
  const messageHtml = messagePayload.html_body || messagePayload.htmlBody || "";
  const messageHtmlDoc = useMemo(() => {
    if (!messageHtml) return "";
    return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <base target="_blank" />
    <style>
      html, body {
        margin: 0;
        padding: 0;
        background: #ffffff;
        color: #0f172a;
        font-family: Arial, sans-serif;
      }
      body {
        padding: 16px;
        overflow-wrap: anywhere;
      }
      img, table {
        max-width: 100%;
      }
      pre {
        white-space: pre-wrap;
      }
      a {
        color: #2563eb;
      }
    </style>
  </head>
  <body>${messageHtml}</body>
</html>`;
  }, [messageHtml]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullWidth
      maxWidth="lg"
      PaperProps={{
        sx: {
          width: "min(1200px, calc(100vw - 32px))",
          maxWidth: "1200px",
        },
      }}
    >
      <DialogTitle sx={{ pb: 1.25 }}>
        <Typography variant="h6" fontWeight={800}>
          {message?.subject || "Email content"}
        </Typography>
        <Box
          sx={{
            mt: 0.5,
            display: "flex",
            alignItems: "center",
            gap: 0.75,
            flexWrap: "wrap",
            color: "text.secondary",
          }}
        >
          <Typography variant="body2">
            {message?.from_name || message?.from_email || "-"}
          </Typography>
          <EastRoundedIcon sx={{ fontSize: 16, opacity: 0.8 }} />
          <Typography variant="body2">
            {message?.to_email || message?.mailbox || "-"}
          </Typography>
          <Box
            component="span"
            sx={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 18,
              lineHeight: 1,
              opacity: 0.72,
              transform: "translateY(-1px)",
            }}
          >
            •
          </Box>
          <Typography variant="body2">
            {formatDateTime(message?.received_at)}
          </Typography>
        </Box>
      </DialogTitle>
      <DialogContent dividers sx={{ p: 0 }}>
        {loading ? (
          <Box sx={{ p: 2.5 }}>
            <Typography>Loading email content...</Typography>
          </Box>
        ) : error ? (
          <Box sx={{ p: 2.5 }}>
            <Alert severity="error">{error}</Alert>
          </Box>
        ) : (
          <Stack spacing={2} sx={{ p: 2.5 }}>
            <Box>
              <Paper
                variant="outlined"
                sx={{
                  p: 1.5,
                  borderRadius: 2,
                  overflow: "hidden",
                  bgcolor: "#f8fafc",
                  borderColor: "rgba(148,163,184,0.28)",
                }}
              >
                {messageHtml ? (
                  <Box
                    component="iframe"
                    title={`email-preview-${message?.id || "message"}`}
                    srcDoc={messageHtmlDoc}
                    sandbox="allow-popups allow-popups-to-escape-sandbox"
                    sx={{
                      width: "100%",
                      minHeight: 620,
                      border: 0,
                      bgcolor: "#ffffff",
                    }}
                  />
                ) : (
                  <Typography
                    component="pre"
                    sx={{
                      m: 0,
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                      fontFamily: "inherit",
                      fontSize: "0.92rem",
                      lineHeight: 1.65,
                      color: "#0f172a",
                    }}
                  >
                    {messageBody || "This email does not have a stored full body yet."}
                  </Typography>
                )}
              </Paper>
            </Box>

            {!messageBody && message?.snippet ? (
              <Alert severity="info">
                This message was ingested before full-body capture was enabled. Only preview text is available.
              </Alert>
            ) : null}
          </Stack>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default MailMessageDialog;
