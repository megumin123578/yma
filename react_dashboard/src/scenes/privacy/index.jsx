import { Box, Divider, Paper, Stack, Typography, useTheme } from "@mui/material";

const PrivacyPage = () => {
  const theme = useTheme();
  const cardBg =
    theme.palette.mode === "dark"
      ? "linear-gradient(180deg, rgba(15,23,42,0.92), rgba(2,6,23,0.9))"
      : "linear-gradient(180deg, #ffffff, #f8fafc)";
  const borderColor =
    theme.palette.mode === "dark"
      ? "rgba(148,163,184,0.25)"
      : "rgba(15,23,42,0.12)";

  return (
    <Box mx="20px" mt="20px" mb="40px">
      <Paper
        elevation={0}
        sx={{
          p: { xs: 3, md: 5 },
          borderRadius: 4,
          border: "1px solid",
          borderColor,
          background: cardBg,
          boxShadow:
            theme.palette.mode === "dark"
              ? "0 20px 50px rgba(2,6,23,0.45)"
              : "0 20px 50px rgba(15,23,42,0.12)",
        }}
      >
        <Stack spacing={2.5} sx={{ maxWidth: 920 }}>
          <Box>
            <Typography variant="h3" fontWeight={800}>
              Privacy Policy
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1}>
              Effective date: 2026-01-30
            </Typography>
          </Box>

          <Typography variant="body1">
            This application provides YouTube analytics and reporting features for
            authenticated users. Your data stays yours, and we only access what is
            needed to operate the service.
          </Typography>

          <Divider />

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              1) Data we access
            </Typography>
            <Typography variant="body1">
              We access Google/YouTube account data only after you grant permission
              via Google OAuth. Requested scopes are limited to read-only analytics
              and channel data required to power dashboards and reports.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              2) How we use data
            </Typography>
            <Typography variant="body1">
              We use the data to show charts, tables, and insights inside the App.
              We do not sell or rent your data to third parties.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              3) Data storage and retention
            </Typography>
            <Typography variant="body1">
              The App may store OAuth tokens and cached analytics to operate
              efficiently. You can revoke access at any time in your Google Account
              permissions.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              4) Data sharing
            </Typography>
            <Typography variant="body1">
              We do not sell your data. We only share data with service providers
              necessary to run the App (such as hosting or security services), and
              only to the extent required to deliver the service.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              5) Security
            </Typography>
            <Typography variant="body1">
              We use reasonable security measures to protect data, including access
              controls and encryption where applicable. No system is 100% secure,
              so we cannot guarantee absolute security.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              6) Data deletion and revocation
            </Typography>
            <Typography variant="body1">
              You can revoke the App's access at any time in your Google Account
              permissions. You may also request deletion of stored data by
              contacting the site owner. We will delete stored data within a
              reasonable timeframe after verification of your request.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              7) Cookies and local storage
            </Typography>
            <Typography variant="body1">
              The App may use cookies or local storage for authentication and
              preferences. You can clear these at any time in your browser settings.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              8) Children's privacy
            </Typography>
            <Typography variant="body1">
              The App is not intended for children under 13. We do not knowingly
              collect personal information from children.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              9) Changes to this policy
            </Typography>
            <Typography variant="body1">
              We may update this policy from time to time. Changes will be posted on
              this page with an updated effective date.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              10) Contact
            </Typography>
            <Typography variant="body1">
              Questions about this policy? Contact the site owner using the email
              listed on the App home page.
            </Typography>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
};

export default PrivacyPage;
