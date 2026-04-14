import { Box, Button, Stack, Typography, useTheme } from "@mui/material";
import { formatNumber } from "./dashboardUtils";

const MetricProgressSection = ({
    title,
    rangeLabel,
    items,
    labelKey,
    valueKey,
    maxValue,
    animateBars,
    gradient,
    canLoadMore,
    onLoadMore,
    sectionSx,
    actionButtonSx,
}) => {
    const theme = useTheme();

    return (
        <Box sx={{ ...sectionSx, p: 3 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>
                {title} ({rangeLabel})
            </Typography>
            {items.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                    No data
                </Typography>
            ) : (
                <>
                    <Stack spacing={1}>
                        {items.map((item) => {
                            const label = item[labelKey];
                            const value = Number(item[valueKey]) || 0;
                            const pct = Math.max(
                                6,
                                Math.round((value / Math.max(1, maxValue)) * 100)
                            );

                            return (
                                <Box key={label}>
                                    <Box display="flex" justifyContent="space-between" mb={0.5}>
                                        <Typography variant="body2">{label}</Typography>
                                        <Typography variant="body2" fontWeight={600}>
                                            {formatNumber(value)}
                                        </Typography>
                                    </Box>
                                    <Box
                                        sx={{
                                            height: 8,
                                            borderRadius: 999,
                                            bgcolor:
                                                theme.palette.mode === "dark"
                                                    ? "rgba(148,163,184,0.2)"
                                                    : "rgba(15,23,42,0.12)",
                                            overflow: "hidden",
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                width: animateBars ? `${pct}%` : 0,
                                                height: "100%",
                                                borderRadius: 999,
                                                background: gradient,
                                                transition: "width 0.5s ease",
                                            }}
                                        />
                                    </Box>
                                </Box>
                            );
                        })}
                    </Stack>
                    {canLoadMore && (
                        <Box mt={2} display="flex" justifyContent="center">
                            <Button
                                size="small"
                                variant="outlined"
                                sx={actionButtonSx}
                                onClick={onLoadMore}
                            >
                                Load more
                            </Button>
                        </Box>
                    )}
                </>
            )}
        </Box>
    );
};

export default MetricProgressSection;
