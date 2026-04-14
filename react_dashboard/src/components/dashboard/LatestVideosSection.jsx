import { Box, Button, Stack, Typography } from "@mui/material";
import InsightsIcon from "@mui/icons-material/Insights";
import { LATEST_VIDEOS_PAGE_SIZE } from "./dashboardUtils";
import { DashboardVideoCard } from "./DashboardVideoCard";

const LatestVideosSection = ({
    sectionSx,
    latestVideos,
    visibleLatestVideos,
    latestVisibleCount,
    canLoadMoreLatestVideos,
    canCollapseLatestVideos,
    onLoadMore,
    onCollapse,
    latestRowSx,
    isDark,
    dashboardPalette,
}) => {
    return (
        <Box mt={4} sx={{ ...sectionSx, p: 4 }}>
            <Box
                display="flex"
                alignItems={{ xs: "flex-start", md: "center" }}
                justifyContent="space-between"
                gap={2}
                mb={3}
                flexWrap="wrap"
            >
                <Typography
                    variant="h5"
                    fontWeight={800}
                    display="flex"
                    alignItems="center"
                    gap={1.5}
                >
                    <InsightsIcon color="primary" /> Latest Video Performance
                </Typography>
                {latestVideos.length > LATEST_VIDEOS_PAGE_SIZE ? (
                    <Stack
                        direction="row"
                        spacing={1}
                        alignItems="center"
                        flexWrap="wrap"
                        useFlexGap
                    >
                        <Typography variant="body2" color="text.secondary">
                            {latestVisibleCount}/{latestVideos.length} videos
                        </Typography>
                        {canLoadMoreLatestVideos ? (
                            <Button size="small" variant="outlined" onClick={onLoadMore}>
                                Xem them
                            </Button>
                        ) : canCollapseLatestVideos ? (
                            <Button size="small" variant="outlined" onClick={onCollapse}>
                                Thu gon
                            </Button>
                        ) : null}
                    </Stack>
                ) : null}
            </Box>
            <Box sx={latestRowSx}>
                {visibleLatestVideos.map((video, idx) => (
                    <DashboardVideoCard
                        key={video.video_id || idx}
                        video={video}
                        index={idx}
                        isDark={isDark}
                        dashboardPalette={dashboardPalette}
                    />
                ))}
            </Box>
        </Box>
    );
};

export default LatestVideosSection;
