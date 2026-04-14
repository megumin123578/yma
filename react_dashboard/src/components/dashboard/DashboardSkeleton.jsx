import { Box, Grid, Skeleton, Stack } from "@mui/material";
import { LATEST_VIDEOS_PAGE_SIZE } from "./dashboardUtils";
import { DashboardVideoCardSkeleton } from "./DashboardVideoCard";

const DashboardSkeleton = ({
    sectionSx,
    statCardSx,
    chartCardSx,
    latestRowSx,
    isDark,
    dashboardPalette,
}) => {
    return (
        <>
            <Box
                mt={2}
                sx={{
                    display: "grid",
                    gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                    gap: 2,
                    width: "100%",
                }}
            >
                {Array.from({ length: 2 }).map((_, sectionIdx) => (
                    <Box key={`dashboard-skeleton-top-${sectionIdx}`} sx={{ display: "flex" }}>
                        <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                            <Skeleton variant="text" width="46%" height={40} sx={{ mb: 2 }} />
                            <Grid container spacing={2} mb={2}>
                                {Array.from({ length: 4 }).map((_, statIdx) => (
                                    <Grid
                                        key={`dashboard-skeleton-stat-${sectionIdx}-${statIdx}`}
                                        size={{ xs: 12, md: 3 }}
                                    >
                                        <Box sx={statCardSx}>
                                            <Skeleton
                                                variant="text"
                                                width="62%"
                                                height={18}
                                                sx={{ mx: "auto" }}
                                            />
                                            <Skeleton
                                                variant="text"
                                                width="54%"
                                                height={36}
                                                sx={{ mx: "auto" }}
                                            />
                                            <Skeleton
                                                variant="text"
                                                width="42%"
                                                height={18}
                                                sx={{ mx: "auto" }}
                                            />
                                        </Box>
                                    </Grid>
                                ))}
                            </Grid>
                            <Grid container spacing={2} sx={{ minWidth: 0 }}>
                                {Array.from({ length: 2 }).map((_, chartIdx) => (
                                    <Grid
                                        key={`dashboard-skeleton-chart-${sectionIdx}-${chartIdx}`}
                                        size={{ xs: 12, md: 6 }}
                                        sx={{ minWidth: 0 }}
                                    >
                                        <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                                            <Skeleton
                                                variant="text"
                                                width="36%"
                                                height={28}
                                                sx={{ mb: 1 }}
                                            />
                                            <Skeleton variant="rounded" height={320} />
                                        </Box>
                                    </Grid>
                                ))}
                            </Grid>
                        </Box>
                    </Box>
                ))}
            </Box>

            <Box
                mt={2}
                sx={{
                    display: "grid",
                    gridTemplateColumns: {
                        xs: "1fr",
                        md: "repeat(2, 1fr)",
                        xl: "repeat(3, 1fr)",
                    },
                    gap: 2,
                    width: "100%",
                }}
            >
                {Array.from({ length: 3 }).map((_, idx) => (
                    <Box key={`dashboard-skeleton-mid-${idx}`} sx={{ ...sectionSx, p: 3 }}>
                        <Skeleton variant="text" width="48%" height={30} sx={{ mb: 1.5 }} />
                        <Stack spacing={1.5}>
                            {Array.from({ length: 5 }).map((_, rowIdx) => (
                                <Box key={`dashboard-skeleton-row-${idx}-${rowIdx}`}>
                                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                                        <Skeleton
                                            variant="text"
                                            width={`${52 + rowIdx * 4}%`}
                                            height={20}
                                        />
                                        <Skeleton variant="text" width="18%" height={20} />
                                    </Box>
                                    <Skeleton variant="rounded" height={8} />
                                </Box>
                            ))}
                        </Stack>
                    </Box>
                ))}
            </Box>

            <Box mt={4} sx={{ ...sectionSx, p: 4 }}>
                <Skeleton variant="text" width="34%" height={40} sx={{ mb: 3 }} />
                <Box sx={latestRowSx}>
                    {Array.from({ length: LATEST_VIDEOS_PAGE_SIZE }).map((_, idx) => (
                        <DashboardVideoCardSkeleton
                            key={`video-skeleton-${idx}`}
                            isDark={isDark}
                            dashboardPalette={dashboardPalette}
                        />
                    ))}
                </Box>
            </Box>
        </>
    );
};

export default DashboardSkeleton;
