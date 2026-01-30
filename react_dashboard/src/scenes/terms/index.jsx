import { Box, Divider, Paper, Stack, Typography, useTheme } from "@mui/material";

const TermsPage = () => {
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
              Terms of Service
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1}>
              Effective date: 2026-01-30
            </Typography>
          </Box>

          <Typography variant="body1">
            By using this App, you agree to these terms. If you do not agree, do
            not use the App.
          </Typography>

          <Divider />

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              1) Use of the App
            </Typography>
            <Typography variant="body1">
              You must use the App in compliance with applicable laws and the
              Google/YouTube API policies.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              2) Accounts and access
            </Typography>
            <Typography variant="body1">
              You are responsible for maintaining the security of your account and
              any access tokens you grant to the App.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              3) User content and data
            </Typography>
            <Typography variant="body1">
              You retain ownership of your content and data. By connecting your
              account, you grant the App permission to access data according to the
              scopes you approved via Google OAuth.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              4) Acceptable use
            </Typography>
            <Typography variant="body1">
              You may not misuse the App, attempt to access non-public areas, or
              interfere with the service. We may suspend access for abuse or policy
              violations.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              5) Availability
            </Typography>
            <Typography variant="body1">
              The App is provided "as is" without warranties of any kind. We may
              modify or discontinue the App at any time.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              6) Limitation of liability
            </Typography>
            <Typography variant="body1">
              To the fullest extent permitted by law, the App is not liable for
              indirect, incidental, or consequential damages arising from your use
              of the service.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              7) Changes to these terms
            </Typography>
            <Typography variant="body1">
              We may update these terms from time to time. Changes will be posted on
              this page with an updated effective date.
            </Typography>
          </Stack>

          <Stack spacing={1.25}>
            <Typography variant="h6" fontWeight={700}>
              8) Contact
            </Typography>
            <Typography variant="body1">
              If you have questions about these terms, contact the site owner via
              the email listed on the App home page.
            </Typography>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
};

export default TermsPage;
