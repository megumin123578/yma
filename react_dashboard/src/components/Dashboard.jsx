import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Grid,
  Card,
  CardMedia,
  CardContent,
  Typography,
  Chip,
  TextField,
  MenuItem,
  CircularProgress,
  useTheme,
} from "@mui/material";
import { motion } from "framer-motion";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import ThumbUpAltOutlinedIcon from "@mui/icons-material/ThumbUpAltOutlined";
import CommentOutlinedIcon from "@mui/icons-material/CommentOutlined";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import { tokens } from "../theme";
import Header from "./Header";
import { API_BASE } from "../config";

const MotionCard = motion.create(Card);

// Variant cho card khi hover
const cardVariants = {
  rest: {
    y: 0,
    boxShadow: "0 4px 12px rgba(0,0,0,0.25)",
    scale: 1,
  },
  hover: {
    y: -4,
    boxShadow: "0 12px 30px rgba(0,0,0,0.35)",
    scale: 1.01,
  },
};

// Variant cho overlay khi hover
const overlayVariants = {
  rest: { opacity: 0, y: 10, pointerEvents: "none" },
  hover: { opacity: 1, y: 0, pointerEvents: "auto" },
};

const VideoList = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const textOnDark = "#fff";
  const apiBase = API_BASE;
  const authHeaders = useMemo(() => {
    const token = localStorage.getItem("access_token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const [channels, setChannels] = useState([]);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [videos, setVideos] = useState([]);
  const [loadingChannels, setLoadingChannels] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [error, setError] = useState("");

  // Fetch danh sách account_tag
  useEffect(() => {
    const fetchChannels = async () => {
      try {
        setLoadingChannels(true);
        const res = await fetch(`${apiBase}/api/video_overview/channels`, {
          headers: authHeaders,
        });
        if (!res.ok) throw new Error("Failed to load channels");
        const data = await res.json();
        setChannels(data.items || []);
        if (data.items && data.items.length > 0) {
          setSelectedChannel(data.items[0].value);
        }
      } catch (err) {
        console.error(err);
        setError(
          "Không load được danh sách kênh. Hãy chạy backend: uvicorn python_backend.main:app --host 0.0.0.0 --port 8000 --reload"
        );
      } finally {
        setLoadingChannels(false);
      }
    };

    fetchChannels();
  }, [apiBase, authHeaders]);

  // Fetch video theo accountTag
  useEffect(() => {
    if (!selectedChannel) return;

    const fetchVideos = async () => {
      try {
        setLoadingVideos(true);
        setError("");
        const res = await fetch(
          `${apiBase}/api/video_overview/videos?accountTag=${encodeURIComponent(
            selectedChannel
          )}`,
          { headers: authHeaders }
        );
        if (!res.ok) throw new Error("Failed to load videos");
        const data = await res.json();
        setVideos(data || []);
      } catch (err) {
        console.error(err);
        setError("Không load được danh sách video.");
      } finally {
        setLoadingVideos(false);
      }
    };

    fetchVideos();
  }, [apiBase, selectedChannel, authHeaders]);

  const formatNumber = (n) => {
    if (n == null) return "-";
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
    if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
    return n.toString();
  };

  const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;

    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const year = d.getFullYear().toString().slice(-2); // "YY"

    return `${day}/${month}/${year}`; // dd/mm/YY
    };


  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Overview" subtitle="Overview Channel Statistic" />

      {/* Filter hàng đầu */}
      <Box
        mb={2}
        display="flex"
        alignItems="center"
        justifyContent="space-between"
        flexWrap="wrap"
        gap={2}
      >
        <Box display="flex" alignItems="center" gap={2}>
          <Typography
            variant="subtitle1"
            color={colors.grey[100]}
            fontWeight={600}
          >
            Choose Channel:
          </Typography>

          {loadingChannels ? (
            <CircularProgress size={20} />
          ) : (
            <TextField
              select
              size="small"
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              sx={{ minWidth: 220 }}
            >
              {channels.map((c) => (
                <MenuItem key={c.value} value={c.value}>
                  {c.label}
                </MenuItem>
              ))}
            </TextField>
          )}
        </Box>

        {videos && videos.length > 0 && (
          <Typography variant="body2" color={colors.grey[300]}>
            Tổng:{" "}
            <span style={{ fontWeight: 600 }}>{videos.length} video</span>
          </Typography>
        )}
      </Box>

      {error && (
        <Typography color="error" mb={2}>
          {error}
        </Typography>
      )}

      {/* Loading */}
      {loadingVideos && videos.length === 0 ? (
        <Box
          mt={4}
          display="flex"
          justifyContent="center"
          alignItems="center"
        >
          <CircularProgress />
        </Box>
      ) : videos.length === 0 ? (
        <Box mt={4} textAlign="center">
          <Typography color={colors.grey[300]}>
            This channel has no data
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={2}>
          {videos.map((v, idx) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={v.video_id}>
                <MotionCard
                  variants={cardVariants}
                  initial="rest"
                  whileHover="hover"
                  transition={{ duration: 0.2, delay: idx * 0.03 }}
                  onClick={() =>
                    window.open(
                      `https://www.youtube.com/watch?v=${v.video_id}`,
                      "_blank"
                    )
                  }
                  sx={{
                    position: "relative",
                    borderRadius: 3,
                    border: "1px solid",
                    borderColor:
                      theme.palette.mode === "dark"
                        ? "rgba(148,163,184,0.2)"
                        : "rgba(15,23,42,0.12)",
                    background:
                      theme.palette.mode === "dark"
                        ? "linear-gradient(140deg, rgba(15,23,42,0.92) 0%, rgba(30,41,59,0.88) 60%, rgba(14,165,233,0.18) 100%)"
                        : "linear-gradient(140deg, rgba(248,250,252,0.96) 0%, rgba(226,232,240,0.92) 55%, rgba(191,219,254,0.6) 100%)",
                    overflow: "hidden",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    height: "100%",
                  }}
                >
                {/* Thumbnail */}
                {v.thumbnail && (
                  <CardMedia
                    component="img"
                    image={v.thumbnail}
                    alt={v.title}
                    sx={{
                      height: 160,
                      objectFit: "cover",
                    }}
                  />
                )}

                {/* Body cơ bản */}
                <CardContent
                  sx={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    gap: 1,
                  }}
                >
                  <Typography
                    variant="subtitle1"
                    color={theme.palette.text.primary}
                    fontWeight={600}
                    noWrap
                    title={v.title}
                  >
                    {v.title}
                  </Typography>

                  <Box display="flex" alignItems="center" gap={1}>
                    <CalendarMonthOutlinedIcon
                      sx={{ fontSize: 16, color: colors.grey[300] }}
                    />
                    <Typography
                      variant="caption"
                      color={colors.grey[300]}
                      sx={{ opacity: 0.8 }}
                    >
                      {formatDate(v.publish_date)}
                    </Typography>
                  </Box>

                  <Box
                    display="flex"
                    alignItems="center"
                    justifyContent="space-between"
                    mt={1}
                  >
                    <Box display="flex" gap={1}>
                      <Chip
                        size="small"
                        icon={
                          <VisibilityOutlinedIcon
                            sx={{ fontSize: 16, color: textOnDark }}
                          />
                        }
                        label={formatNumber(v.views)}
                        sx={{
                          bgcolor: colors.primary[500],
                          color: textOnDark,
                          "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                        }}
                      />
                      <Chip
                        size="small"
                        icon={
                          <ThumbUpAltOutlinedIcon
                            sx={{ fontSize: 16, color: textOnDark }}
                          />
                        }
                        label={formatNumber(v.likes)}
                        sx={{
                          bgcolor: colors.primary[500],
                          color: textOnDark,
                          "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                        }}
                      />
                      <Chip
                        size="small"
                        icon={
                          <CommentOutlinedIcon
                            sx={{ fontSize: 16, color: textOnDark }}
                          />
                        }
                        label={formatNumber(v.comments)}
                        sx={{
                          bgcolor: colors.primary[500],
                          color: textOnDark,
                          "& .MuiChip-icon": { ml: 0.5, color: textOnDark },
                        }}
                      />
                    </Box>
                  </Box>
                </CardContent>

                {/* ================== OVERLAY CHI TIẾT KHI HOVER ================== */}
                <Box
                  component={motion.div}
                  variants={overlayVariants}
                  sx={{
                    position: "absolute",
                    inset: 0,
                    bgcolor: "rgba(0,0,0,0.9)",
                    color: textOnDark,
                    p: 2,
                    display: "flex",
                    flexDirection: "column",
                    gap: 0.5,
                    zIndex: 2,
                    "& .MuiTypography-root": {
                      fontSize: "0.9rem",
                    },
                  }}
                >
                  <Box mt={1} />

                  <Typography variant="caption">
                    <strong>Engaged views:</strong>{" "}
                    {formatNumber(v.engaged_views)}
                  </Typography>

                  <Box mt={1} />

                  <Typography variant="caption">
                    <strong>Annotation CTR:</strong>{" "}
                    {v.annotation_click_through_rate ?? "-"}
                  </Typography>
                  <Typography variant="caption">
                    <strong>Annotation close rate:</strong>{" "}
                    {v.annotation_close_rate ?? "-"}
                  </Typography>
                  <Typography variant="caption">
                    <strong>Avg view duration (s):</strong>{" "}
                    {v.average_view_duration_seconds ?? "-"}
                  </Typography>
                  <Typography variant="caption">
                    <strong>Shares:</strong> {formatNumber(v.shares)}
                  </Typography>
                  <Typography variant="caption">
                    <strong>Subscribers gained:</strong>{" "}
                    {formatNumber(v.subscribers_gained)}
                  </Typography>
                  <Typography variant="caption">
                    <strong>Subscribers lost:</strong>{" "}
                    {formatNumber(v.subscribers_lost)}
                  </Typography>

                  <Box mt={1} />
                </Box>
                {/* ================== END OVERLAY ================== */}
              </MotionCard>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );
};

export default VideoList;
