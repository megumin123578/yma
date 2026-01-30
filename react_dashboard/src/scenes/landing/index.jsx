import { useRef } from "react";
import { Link } from "react-router-dom";
import {
  Box,
  Button,
  Container,
  Grid,
  Typography,
  useTheme,
  Stack,
  alpha,
  Paper,
} from "@mui/material";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import {
  TrendingUp,
  BarChart,
  People,
  MonetizationOn,
  Security,
  Speed,
  ArrowForward,
  CheckCircle,
} from "@mui/icons-material";

const FeatureCard = ({ icon: Icon, title, description, delay }) => {
  const theme = useTheme();

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      viewport={{ once: true }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 4,
          height: "100%",
          borderRadius: 4,
          background:
            theme.palette.mode === "dark"
              ? alpha(theme.palette.background.paper, 0.4)
              : alpha("#ffffff", 0.6),
          backdropFilter: "blur(20px)",
          border: "1px solid",
          borderColor:
            theme.palette.mode === "dark"
              ? "rgba(255, 255, 255, 0.1)"
              : "rgba(0, 0, 0, 0.05)",
          transition: "all 0.3s ease",
          "&:hover": {
            transform: "translateY(-8px)",
            boxShadow: theme.shadows[10],
            borderColor: theme.palette.primary.main,
          },
        }}
      >
        <Box
          sx={{
            display: "inline-flex",
            p: 1.5,
            borderRadius: 2,
            mb: 2,
            background:
              theme.palette.mode === "dark"
                ? "linear-gradient(135deg, rgba(56,189,248,0.2) 0%, rgba(99,102,241,0.2) 100%)"
                : "linear-gradient(135deg, rgba(56,189,248,0.1) 0%, rgba(99,102,241,0.1) 100%)",
            color: theme.palette.mode === "dark" ? "#38bdf8" : "#2563eb",
          }}
        >
          <Icon fontSize="medium" />
        </Box>
        <Typography variant="h5" fontWeight={700} gutterBottom>
          {title}
        </Typography>
        <Typography variant="body1" color="text.secondary" lineHeight={1.6}>
          {description}
        </Typography>
      </Paper>
    </motion.div>
  );
};



const LandingPage = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  const heroBg = isDark
    ? "radial-gradient(circle at 50% 0%, #1e1b4b 0%, #0f172a 100%)"
    : "radial-gradient(circle at 50% 0%, #e0f2fe 0%, #f8fafc 100%)";

  return (
    <Box
      sx={{
        minHeight: "100vh",
        background: isDark ? "#0f172a" : "#f8fafc",
        overflowX: "hidden",
        position: "relative",
      }}
    >
      {/* Scroll Progress Bar */}
      <motion.div
        style={{
          scaleX,
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          height: 4,
          background: "linear-gradient(90deg, #38bdf8, #818cf8, #c084fc)",
          transformOrigin: "0%",
          zIndex: 9999,
        }}
      />

      {/* Hero Section */}
      <Box
        sx={{
          position: "relative",
          pt: { xs: 12, md: 24 },
          pb: { xs: 12, md: 20 },
          background: heroBg,
          overflow: "hidden",
        }}
      >
        {/* Animated Background Shapes */}
        <Box
          component={motion.div}
          animate={{
            y: [0, -20, 0],
            rotate: [0, 5, 0],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          sx={{
            position: "absolute",
            top: "10%",
            left: "5%",
            width: "40vw",
            height: "40vw",
            borderRadius: "50%",
            background: isDark
              ? "radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%)"
              : "radial-gradient(circle, rgba(56,189,248,0.25) 0%, transparent 70%)",
            filter: "blur(60px)",
            zIndex: 0,
          }}
        />
        <Box
          component={motion.div}
          animate={{
            y: [0, 30, 0],
            x: [0, -20, 0],
          }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          sx={{
            position: "absolute",
            bottom: "10%",
            right: "5%",
            width: "35vw",
            height: "35vw",
            borderRadius: "50%",
            background: isDark
              ? "radial-gradient(circle, rgba(168,85,247,0.12) 0%, transparent 70%)"
              : "radial-gradient(circle, rgba(168,85,247,0.2) 0%, transparent 70%)",
            filter: "blur(80px)",
            zIndex: 0,
          }}
        />

        <Container maxWidth="lg" sx={{ position: "relative", zIndex: 1 }}>
          <Stack spacing={4} alignItems="center" textAlign="center">
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="overline"
                sx={{
                  fontWeight: 700,
                  letterSpacing: 2,
                  color: isDark ? "#38bdf8" : "#0284c7",
                  bgcolor: isDark ? "rgba(56,189,248,0.1)" : "rgba(2,132,199,0.1)",
                  px: 2,
                  py: 0.5,
                  borderRadius: 10,
                  display: "inline-block",
                  mb: 2,
                }}
              >
                PRO YOUTUBE ANALYTICS
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography
                variant="h1"
                sx={{
                  fontSize: { xs: 40, md: 72 },
                  fontWeight: 900,
                  lineHeight: 1.1,
                  background: isDark
                    ? "linear-gradient(to right, #ffffff 30%, #94a3b8 100%)"
                    : "linear-gradient(to right, #0f172a 30%, #475569 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  mb: 2,
                }}
              >
                FMC
              </Typography>
            </Box>

            <Box sx={{ mb: 4 }}>
              <Typography
                variant="h5"
                color="text.secondary"
                sx={{ maxWidth: 700, mx: "auto", lineHeight: 1.6 }}
              >
                FMC helps content creators visualize and analyze their channel performance. By securely connecting to your YouTube Analytics data via the official YouTube API, we provide detailed insights into views, revenue, traffic sources, and audience demographics to encourage data-driven growth.
              </Typography>
            </Box>

            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Read our <Link to="/privacy" style={{ color: "#38bdf8", textDecoration: "underline" }}>Privacy Policy</Link>.
              </Typography>
            </Box>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
            >
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2} pt={2}>
                <Button
                  component={Link}
                  to="/login"
                  variant="contained"
                  size="large"
                  endIcon={<ArrowForward />}
                  sx={{
                    px: 5,
                    py: 1.8,
                    fontSize: "1.1rem",
                    borderRadius: 30,
                    textTransform: "none",
                    background: "linear-gradient(90deg, #38bdf8, #6366f1)",
                    boxShadow: "0 10px 40px -10px rgba(99,102,241,0.5)",
                    "&:hover": {
                      background: "linear-gradient(90deg, #60a5fa, #7c3aed)",
                      transform: "translateY(-2px)",
                      boxShadow: "0 20px 40px -10px rgba(99,102,241,0.6)",
                    },
                  }}
                >
                  Get Started
                </Button>
                <Button
                  component={Link}
                  to="/register"
                  variant="outlined"
                  size="large"
                  sx={{
                    px: 5,
                    py: 1.8,
                    fontSize: "1.1rem",
                    borderRadius: 30,
                    textTransform: "none",
                    borderWidth: 2,
                    borderColor: isDark ? "rgba(255,255,255,0.2)" : "rgba(0,0,0,0.1)",
                    color: "text.primary",
                    "&:hover": {
                      borderColor: theme.palette.primary.main,
                      borderWidth: 2,
                      bgcolor: alpha(theme.palette.primary.main, 0.05),
                    },
                  }}
                >
                  Create Account
                </Button>
              </Stack>
            </motion.div>
          </Stack>
        </Container>
      </Box>




      {/* Explicit About Section for Verification */}
      <Container maxWidth="md" sx={{ py: 6, textAlign: "left" }}>
        <Box mb={4}>
          <Typography variant="h4" fontWeight={800} gutterBottom>
            About FMC
          </Typography>
          <Typography variant="body1" paragraph>
            FMC is a dedicated dashboard application designed to help YouTube content creators understand their performance metrics.
          </Typography>
          <Typography variant="body1" paragraph>
            <strong>Purpose:</strong> Our application retrieves analytic data from your YouTube channel (such as views, subscribers, watch time, and revenue) using the YouTube Analytics API. This allows us to present comprehensive charts, comparison tools, and insights that go beyond the standard YouTube Studio interface.
          </Typography>
          <Typography variant="body1" paragraph>
            <strong>Google Sign-In:</strong> We use Google Sign-In to securely authenticate you and obtain the necessary read-only permissions to fetch your channel's analytics data. We do not modify your videos or channel settings.
          </Typography>
          <Typography variant="body1" paragraph>
            <strong>Privacy Policy:</strong> <Link to="/privacy" style={{ color: "#38bdf8", textDecoration: "underline" }}>Read our Privacy Policy</Link> to learn more about how we handle your data.
          </Typography>

          <Box mt={2}>
            <Typography variant="body2">
              Read our <Link to="/privacy" style={{ color: "#38bdf8", textDecoration: "underline" }}>Privacy Policy</Link> to learn more about how we handle your data.
            </Typography>
          </Box>
        </Box>
      </Container>


      {/* Features Section */}
      <Container maxWidth="lg" sx={{ py: 10 }}>
        <Box textAlign="center" mb={8}>
          <Typography variant="overline" color="primary" fontWeight={700} letterSpacing={1.5}>
            FEATURES
          </Typography>
          <Typography variant="h2" fontWeight={800} mt={1} mb={2}>
            Everything you need to grow
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ maxWidth: 600, mx: "auto" }}>
            Comprehensive tools to deep dive into your channel's performance.
          </Typography>
        </Box>

        <Grid container spacing={4}>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.1}
              icon={TrendingUp}
              title="Deep Analytics"
              description="Go beyond basic views. Analyze watch time, retention rates, and engagement metrics with detailed, interactive charts."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.2}
              icon={People}
              title="Audience Insights"
              description="Understand who watches your videos. Demographics, geography, and active times to help you publish when it matters."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.3}
              icon={MonetizationOn}
              title="Revenue Tracking"
              description="Track your estimated revenue, CPM, and RPM across different videos to identify your most profitable content."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.4}
              icon={BarChart}
              title="Traffic Sources"
              description="Discover how viewers find you. Search trends, suggested videos, and external sites driving traffic to your channel."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.5}
              icon={Speed}
              title="Performance Benchmarks"
              description="Compare your current performance against your historical data to stay on track with your growth goals."
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FeatureCard
              delay={0.6}
              icon={Security}
              title="Secure & Private"
              description="Your data is yours. We use official YouTube APIs with secure Oauth2 authentication. You are in full control."
            />
          </Grid>
        </Grid>
      </Container>

      {/* CTA Section */}
      <Box sx={{ py: 15, position: "relative", overflow: "hidden" }}>
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            background: isDark
              ? "linear-gradient(180deg, transparent 0%, rgba(56,189,248,0.05) 100%)"
              : "linear-gradient(180deg, transparent 0%, rgba(56,189,248,0.05) 100%)",
            zIndex: 0
          }}
        />
        <Container maxWidth="md" sx={{ position: "relative", zIndex: 1, textAlign: "center" }}>
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
          >
            <Typography variant="h2" fontWeight={800} mb={3}>
              Ready to scale your channel?
            </Typography>

            <Button
              component={Link}
              to="/register"
              variant="contained"
              size="large"
              sx={{
                px: 6,
                py: 2,
                fontSize: "1.2rem",
                borderRadius: 4,
                fontWeight: 700,
                background: "linear-gradient(90deg, #38bdf8, #6366f1)",
                boxShadow: "0 20px 40px -10px rgba(56,189,248,0.5)",
                "&:hover": {
                  transform: "translateY(-3px)",
                  background: "linear-gradient(90deg, #60a5fa, #7c3aed)",
                  boxShadow: "0 25px 50px -12px rgba(56,189,248,0.6)",
                },
              }}
            >
              Start
            </Button>
          </motion.div>
        </Container>
      </Box>

      {/* Footer */}
      <Box
        component="footer"
        sx={{
          py: 4,
          borderTop: "1px solid",
          borderColor: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)",
          textAlign: "center",
        }}
      >
        <Container maxWidth="lg">
          <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems="center" spacing={2}>
            <Typography variant="body2" color="text.secondary">
              (C) {new Date().getFullYear()} FMC. All rights reserved.
            </Typography>
            <Stack direction="row" spacing={3}>
              <Link to="/privacy" style={{ textDecoration: "none" }}>
                <Typography variant="body2" color="text.secondary" sx={{ "&:hover": { color: "primary.main" } }}>
                  Privacy Policy
                </Typography>
              </Link>
              <Link to="/terms" style={{ textDecoration: "none" }}>
                <Typography variant="body2" color="text.secondary" sx={{ "&:hover": { color: "primary.main" } }}>
                  Terms of Service
                </Typography>
              </Link>
            </Stack>
          </Stack>
        </Container>
      </Box>
    </Box>
  );
};

export default LandingPage;
