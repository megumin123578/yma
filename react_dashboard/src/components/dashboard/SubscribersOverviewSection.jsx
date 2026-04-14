import { Box, Grid, Typography } from "@mui/material";
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import {
    formatDateFull,
    formatDateMonth,
    formatNumber,
} from "./dashboardUtils";

const SubscribersOverviewSection = ({
    rangeLabel,
    sectionSx,
    statCardSx,
    chartCardSx,
    subscribersSeries,
    subscribersSummary,
    pctColor,
    formatPct,
    subscribersXAxisTicks,
    chartTooltipStyles,
    dashboardPalette,
}) => {
    return (
        <Box sx={{ display: "flex" }}>
            <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                <Typography variant="h5" fontWeight={700} mb={2}>
                    Subscribers ({rangeLabel})
                </Typography>
                {subscribersSeries.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                        No data
                    </Typography>
                ) : (
                    <>
                        <Grid container spacing={2} mb={2}>
                            <Grid size={{ xs: 12, md: 3 }}>
                                <Box sx={statCardSx}>
                                    <Typography variant="body2" color="text.secondary">
                                        Gained
                                    </Typography>
                                    <Typography variant="h5" fontWeight={700}>
                                        {formatNumber(subscribersSummary.stats.gained)}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{ color: pctColor(subscribersSummary.stats.gainedPct) }}
                                    >
                                        {formatPct(subscribersSummary.stats.gainedPct)}
                                    </Typography>
                                </Box>
                            </Grid>
                            <Grid size={{ xs: 12, md: 3 }}>
                                <Box sx={statCardSx}>
                                    <Typography variant="body2" color="text.secondary">
                                        Lost
                                    </Typography>
                                    <Typography variant="h5" fontWeight={700}>
                                        {formatNumber(subscribersSummary.stats.lost)}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{ color: pctColor(-subscribersSummary.stats.lostPct) }}
                                    >
                                        {formatPct(subscribersSummary.stats.lostPct)}
                                    </Typography>
                                </Box>
                            </Grid>
                            <Grid size={{ xs: 12, md: 3 }}>
                                <Box sx={statCardSx}>
                                    <Typography variant="body2" color="text.secondary">
                                        Change
                                    </Typography>
                                    <Typography variant="h5" fontWeight={700}>
                                        {formatNumber(subscribersSummary.stats.change)}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{ color: pctColor(subscribersSummary.stats.changePct) }}
                                    >
                                        {formatPct(subscribersSummary.stats.changePct)}
                                    </Typography>
                                </Box>
                            </Grid>
                            <Grid size={{ xs: 12, md: 3 }}>
                                <Box sx={statCardSx}>
                                    <Typography variant="body2" color="text.secondary">
                                        Avg daily change
                                    </Typography>
                                    <Typography variant="h5" fontWeight={700}>
                                        {formatNumber(Math.round(subscribersSummary.stats.avg))}
                                    </Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{ color: pctColor(subscribersSummary.stats.avgPct) }}
                                    >
                                        {formatPct(subscribersSummary.stats.avgPct)}
                                    </Typography>
                                </Box>
                            </Grid>
                        </Grid>

                        <Grid container spacing={2} sx={{ minWidth: 0 }}>
                            <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                                <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                                    <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                                        Gained
                                    </Typography>
                                    <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                                        <ResponsiveContainer
                                            width="100%"
                                            height={320}
                                            minWidth={0}
                                            minHeight={0}
                                        >
                                            <BarChart
                                                data={subscribersSummary.chart}
                                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                                            >
                                                <CartesianGrid
                                                    stroke="rgba(148,163,184,0.2)"
                                                    strokeDasharray="3 3"
                                                />
                                                <XAxis
                                                    dataKey="day"
                                                    tick={{ fontSize: 11 }}
                                                    ticks={subscribersXAxisTicks}
                                                    tickFormatter={formatDateMonth}
                                                    allowDuplicatedCategory={false}
                                                />
                                                <YAxis tickFormatter={formatNumber} />
                                                <Tooltip
                                                    {...chartTooltipStyles}
                                                    labelFormatter={formatDateFull}
                                                />
                                                <Bar
                                                    dataKey="gained"
                                                    fill={dashboardPalette.positive}
                                                    radius={[6, 6, 0, 0]}
                                                />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </Box>
                                </Box>
                            </Grid>
                            <Grid size={{ xs: 12, md: 6 }} sx={{ minWidth: 0 }}>
                                <Box sx={{ ...chartCardSx, minWidth: 0, width: "100%" }}>
                                    <Typography variant="subtitle1" fontWeight={700} mb={0.5}>
                                        Change
                                    </Typography>
                                    <Box sx={{ width: "100%", minWidth: 0, minHeight: 0 }}>
                                        <ResponsiveContainer
                                            width="100%"
                                            height={320}
                                            minWidth={0}
                                            minHeight={0}
                                        >
                                            <BarChart
                                                data={subscribersSummary.chart}
                                                margin={{ top: 4, right: 6, left: -30, bottom: -6 }}
                                            >
                                                <CartesianGrid
                                                    stroke="rgba(148,163,184,0.2)"
                                                    strokeDasharray="3 3"
                                                />
                                                <XAxis
                                                    dataKey="day"
                                                    tick={{ fontSize: 11 }}
                                                    ticks={subscribersXAxisTicks}
                                                    tickFormatter={formatDateMonth}
                                                    allowDuplicatedCategory={false}
                                                />
                                                <YAxis tickFormatter={formatNumber} />
                                                <Tooltip
                                                    {...chartTooltipStyles}
                                                    labelFormatter={formatDateFull}
                                                />
                                                <Bar
                                                    dataKey="change"
                                                    fill={dashboardPalette.accentSoft}
                                                    radius={[6, 6, 0, 0]}
                                                />
                                            </BarChart>
                                        </ResponsiveContainer>
                                    </Box>
                                </Box>
                            </Grid>
                        </Grid>
                    </>
                )}
            </Box>
        </Box>
    );
};

export default SubscribersOverviewSection;
