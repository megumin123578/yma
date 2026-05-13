import { Box, Typography, useTheme } from "@mui/material";
import { alpha } from "@mui/material/styles";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";

const NoAccessPage = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const accent = isDark ? "#7de0d2" : theme.palette.primary.main;

  return (
    <Box
      sx={{
        minHeight: "70vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 3,
      }}
    >
      <Box
        sx={{
          maxWidth: 460,
          width: "100%",
          textAlign: "center",
          p: { xs: 3, sm: 5 },
          borderRadius: 4,
          border: `1px solid ${isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.08)"}`,
          bgcolor: isDark ? "rgba(15,23,42,0.55)" : "#ffffff",
          boxShadow: isDark
            ? "0 24px 60px rgba(0,0,0,0.45)"
            : "0 18px 40px rgba(15,23,42,0.08)",
        }}
      >
        <Box
          sx={{
            width: 72,
            height: 72,
            mx: "auto",
            mb: 2,
            borderRadius: "50%",
            bgcolor: alpha(accent, 0.12),
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: accent,
          }}
        >
          <LockOutlinedIcon sx={{ fontSize: 36 }} />
        </Box>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
          Permission required
        </Typography>
        <Typography variant="body2" color="text.secondary">
          You don't have access to this page yet.
        </Typography>
      </Box>
    </Box>
  );
};

export default NoAccessPage;
