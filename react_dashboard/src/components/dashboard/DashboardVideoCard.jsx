import {
    Box,
    Button,
    Card,
    CardContent,
    CardMedia,
    Grid,
    Skeleton,
    Stack,
    Typography,
} from "@mui/material";
import { motion } from "framer-motion";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import AssessmentOutlinedIcon from "@mui/icons-material/AssessmentOutlined";
import {
    formatDate,
    formatDuration,
    formatNumber,
    formatRate,
} from "./dashboardUtils";

const MotionCard = motion.create(Card);

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

const overlayVariants = {
    rest: { opacity: 0, y: "100%", pointerEvents: "none" },
    hover: { opacity: 1, y: 0, pointerEvents: "auto" },
};

export const DashboardVideoCard = ({ video, index, isDark, dashboardPalette }) => {
    return (
        <Box sx={{ width: "100%" }}>
            <MotionCard
                variants={cardVariants}
                initial="rest"
                whileHover="hover"
                transition={{ duration: 0.3, delay: index * 0.05 }}
                onClick={() =>
                    window.open(`https://www.youtube.com/watch?v=${video.video_id}`, "_blank")
                }
                sx={{
                    position: "relative",
                    borderRadius: 4,
                    border: "1px solid",
                    borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(15,23,42,0.1)",
                    background: dashboardPalette.surface,
                    overflow: "hidden",
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    height: "100%",
                    boxShadow: isDark
                        ? "0 10px 30px rgba(0,0,0,0.3)"
                        : "0 8px 24px rgba(148,163,184,0.1)",
                }}
            >
                <Box sx={{ position: "relative", overflow: "hidden" }}>
                    {video.thumbnail && (
                        <CardMedia
                            component="img"
                            image={video.thumbnail}
                            alt={video.title}
                            sx={{
                                width: "100%",
                                aspectRatio: "16/9",
                                objectFit: "cover",
                                transition: "transform 0.5s ease",
                                ".MuiCard-root:hover &": { transform: "scale(1.08)" },
                            }}
                        />
                    )}
                    <Box
                        sx={{
                            position: "absolute",
                            top: 10,
                            right: 10,
                            bgcolor: dashboardPalette.badgeBg,
                            color: dashboardPalette.white,
                            px: 1.2,
                            py: 0.5,
                            borderRadius: 1.5,
                            fontSize: "0.65rem",
                            fontWeight: 800,
                            backdropFilter: "blur(4px)",
                            border: `1px solid ${dashboardPalette.badgeBorder}`,
                            zIndex: 2,
                        }}
                    >
                        {formatDate(video.publish_date)}
                    </Box>
                    <Box
                        className="play-overlay"
                        sx={{
                            position: "absolute",
                            inset: 0,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            bgcolor: dashboardPalette.playOverlayBg,
                            opacity: 0,
                            transition: "opacity 0.3s ease",
                            zIndex: 1,
                            ".MuiCard-root:hover &": { opacity: 1 },
                        }}
                    >
                        <Box
                            sx={{
                                width: 50,
                                height: 50,
                                borderRadius: "50%",
                                bgcolor: dashboardPalette.playButtonBg,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                backdropFilter: "blur(8px)",
                                border: `1px solid ${dashboardPalette.playButtonBorder}`,
                            }}
                        >
                            <PlayArrowRoundedIcon
                                sx={{ fontSize: 32, color: dashboardPalette.white }}
                            />
                        </Box>
                    </Box>
                </Box>

                <CardContent
                    sx={{ p: 2, flex: 1, display: "flex", flexDirection: "column" }}
                >
                    <Typography
                        variant="body1"
                        color="text.primary"
                        fontWeight={700}
                        sx={{
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                            lineHeight: 1.3,
                            mb: 2,
                            minHeight: "2.6em",
                            fontSize: "0.92rem",
                        }}
                    >
                        {video.title}
                    </Typography>

                    <Box
                        mt="auto"
                        sx={{
                            display: "grid",
                            gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                            gap: 1,
                        }}
                    >
                        <Box sx={{ minWidth: 0 }}>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                display="block"
                                sx={{ fontSize: "0.7rem" }}
                            >
                                Views
                            </Typography>
                            <Typography
                                variant="body2"
                                fontWeight={700}
                                display="flex"
                                alignItems="center"
                                gap={0.5}
                            >
                                {formatNumber(video.views)}
                                <TrendingUpIcon
                                    sx={{ fontSize: 14, color: dashboardPalette.positive }}
                                />
                            </Typography>
                        </Box>
                        <Box sx={{ minWidth: 0 }}>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                display="block"
                                sx={{ fontSize: "0.7rem" }}
                            >
                                Likes
                            </Typography>
                            <Typography variant="body2" fontWeight={700}>
                                {formatNumber(video.likes)}
                            </Typography>
                        </Box>
                        <Box sx={{ minWidth: 0 }}>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                display="block"
                                sx={{ fontSize: "0.7rem" }}
                            >
                                CTR
                            </Typography>
                            <Typography variant="body2" fontWeight={700} color="info.main">
                                {formatRate(video.thumbnail_ctr)}
                            </Typography>
                        </Box>
                        <Box sx={{ minWidth: 0 }}>
                            <Typography
                                variant="caption"
                                color="text.secondary"
                                display="block"
                                sx={{ fontSize: "0.7rem" }}
                            >
                                Eng.
                            </Typography>
                            <Typography
                                variant="body2"
                                fontWeight={700}
                                color="primary.main"
                            >
                                {formatRate(video.engagementRate)}
                            </Typography>
                        </Box>
                    </Box>
                </CardContent>

                <Box
                    component={motion.div}
                    variants={overlayVariants}
                    transition={{ type: "spring", damping: 25, stiffness: 120 }}
                    sx={{
                        position: "absolute",
                        inset: 0,
                        background: dashboardPalette.surfaceStrong,
                        backdropFilter: "blur(12px)",
                        p: 2.5,
                        display: "flex",
                        flexDirection: "column",
                        zIndex: 3,
                    }}
                >
                    <Typography
                        variant="subtitle2"
                        fontWeight={800}
                        mb={2}
                        color="primary"
                        sx={{ display: "flex", alignItems: "center", gap: 1 }}
                    >
                        <AssessmentOutlinedIcon fontSize="small" />
                        Performance Details
                    </Typography>
                    <Grid container spacing={1.5}>
                        {[
                            {
                                label: "Engaged views",
                                val: formatNumber(video.engaged_views),
                            },
                            { label: "Shares", val: formatNumber(video.shares) },
                            {
                                label: "Sub. Gained",
                                val: formatNumber(video.subscribers_gained),
                            },
                            {
                                label: "Sub. Lost",
                                val: formatNumber(video.subscribers_lost),
                            },
                            {
                                label: "Avg Duration",
                                val: formatDuration(video.average_view_duration_seconds),
                            },
                            {
                                label: "Thumbnail CTR",
                                val: formatRate(video.thumbnail_ctr),
                            },
                        ].map((item) => (
                            <Grid size={{ xs: 6 }} key={item.label}>
                                <Typography
                                    variant="caption"
                                    color="text.secondary"
                                    display="block"
                                    sx={{
                                        fontSize: "0.65rem",
                                        textTransform: "uppercase",
                                        letterSpacing: 0.5,
                                    }}
                                >
                                    {item.label}
                                </Typography>
                                <Typography variant="body2" fontWeight={700}>
                                    {item.val}
                                </Typography>
                            </Grid>
                        ))}
                    </Grid>
                    <Box mt="auto">
                        <Button
                            fullWidth
                            variant="contained"
                            size="small"
                            startIcon={<PlayArrowRoundedIcon />}
                            sx={{
                                borderRadius: 2,
                                textTransform: "none",
                                background: `linear-gradient(90deg, ${dashboardPalette.info}, ${dashboardPalette.accentAlt})`,
                            }}
                        >
                            Watch on YouTube
                        </Button>
                    </Box>
                </Box>
            </MotionCard>
        </Box>
    );
};

export const DashboardVideoCardSkeleton = ({ isDark, dashboardPalette }) => {
    return (
        <Box sx={{ width: "100%" }}>
            <Card
                sx={{
                    position: "relative",
                    borderRadius: 4,
                    border: "1px solid",
                    borderColor: isDark ? "rgba(255,255,255,0.1)" : "rgba(15,23,42,0.1)",
                    background: dashboardPalette.surface,
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                    height: "100%",
                    boxShadow: isDark
                        ? "0 10px 30px rgba(0,0,0,0.3)"
                        : "0 8px 24px rgba(148,163,184,0.1)",
                }}
            >
                <Skeleton variant="rectangular" sx={{ width: "100%", aspectRatio: "16/9" }} />
                <CardContent
                    sx={{ p: 2, flex: 1, display: "flex", flexDirection: "column" }}
                >
                    <Skeleton variant="text" height={28} sx={{ mb: 0.25 }} />
                    <Skeleton variant="text" width="74%" height={28} sx={{ mb: 2 }} />
                    <Stack direction="row" spacing={1} justifyContent="space-between" mt="auto">
                        {Array.from({ length: 3 }).map((_, metricIdx) => (
                            <Box
                                key={`video-skeleton-metric-${metricIdx}`}
                                sx={{ minWidth: 0, flex: 1 }}
                            >
                                <Skeleton variant="text" width="70%" height={16} />
                                <Skeleton variant="text" width="82%" height={22} />
                            </Box>
                        ))}
                    </Stack>
                </CardContent>
            </Card>
        </Box>
    );
};
