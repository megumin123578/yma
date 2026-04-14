import { Box, Typography, useTheme } from "@mui/material";
import {
    CartesianGrid,
    Line,
    LineChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import {
    formatCurrency,
    formatDate,
    formatDateMonth,
} from "./dashboardUtils";

const RevenueOverviewSection = ({
    rangeLabel,
    sectionSx,
    revenueRows,
    revenueMetricCards,
    revenueChartData,
    revenueXAxisTicks,
    chartTooltipStyles,
    dashboardPalette,
}) => {
    const theme = useTheme();

    return (
        <Box sx={{ display: "flex" }}>
            <Box sx={{ ...sectionSx, p: 4, minHeight: 560, width: "100%" }}>
                <Typography variant="subtitle1" fontWeight={700} mb={1}>
                    Revenue ({rangeLabel})
                </Typography>
                {revenueRows.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                        No data
                    </Typography>
                ) : (
                    <>
                        <Box
                            sx={{
                                display: "grid",
                                gridTemplateColumns: {
                                    xs: "1fr",
                                    sm: "1fr 1fr",
                                    lg: "repeat(3, minmax(0, 1fr))",
                                },
                                columnGap: 2,
                                rowGap: 0.5,
                                mb: 2,
                            }}
                        >
                            {revenueMetricCards.map((item) => (
                                <Box
                                    key={item.label}
                                    sx={{
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "space-between",
                                        gap: 1.5,
                                        py: 1,
                                        borderBottom: "1px solid",
                                        borderColor:
                                            theme.palette.mode === "dark"
                                                ? "rgba(148,163,184,0.14)"
                                                : "rgba(15,23,42,0.08)",
                                    }}
                                >
                                    <Box
                                        sx={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: 1,
                                            minWidth: 0,
                                        }}
                                    >
                                        <Box
                                            sx={{
                                                width: 8,
                                                height: 8,
                                                borderRadius: "50%",
                                                bgcolor: item.color,
                                                flexShrink: 0,
                                            }}
                                        />
                                        <Typography
                                            variant="body2"
                                            color="text.secondary"
                                            sx={{ lineHeight: 1.35 }}
                                        >
                                            {item.label}
                                        </Typography>
                                    </Box>
                                    <Typography
                                        variant="body2"
                                        fontWeight={700}
                                        sx={{ whiteSpace: "nowrap", flexShrink: 0 }}
                                    >
                                        {item.value}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>
                        {revenueChartData.length > 0 && (
                            <Box mt={2} sx={{ ml: -3, minWidth: 0, width: "100%" }}>
                                <ResponsiveContainer
                                    width="100%"
                                    height={320}
                                    minWidth={0}
                                    minHeight={0}
                                >
                                    <LineChart data={revenueChartData}>
                                        <CartesianGrid
                                            strokeDasharray="3 3"
                                            stroke={
                                                theme.palette.mode === "dark"
                                                    ? "rgba(148,163,184,0.2)"
                                                    : "rgba(15,23,42,0.1)"
                                            }
                                        />
                                        <XAxis
                                            dataKey="day"
                                            ticks={revenueXAxisTicks}
                                            tickFormatter={formatDateMonth}
                                            tick={{ fontSize: 11 }}
                                            interval={0}
                                            allowDuplicatedCategory={false}
                                        />
                                        <YAxis
                                            tickFormatter={(value) => formatCurrency(value)}
                                            tick={{ fontSize: 11 }}
                                        />
                                        <Tooltip
                                            formatter={(value, name) => [
                                                formatCurrency(value),
                                                name,
                                            ]}
                                            labelFormatter={formatDate}
                                            contentStyle={chartTooltipStyles.contentStyle}
                                            labelStyle={chartTooltipStyles.labelStyle}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="estimated"
                                            name="Estimated Revenue"
                                            stroke={dashboardPalette.revenueMetricColors.estimated}
                                            strokeWidth={2}
                                            dot={false}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="ad"
                                            name="Estimated Ad Revenue"
                                            stroke={dashboardPalette.revenueMetricColors.ad}
                                            strokeWidth={2}
                                            dot={false}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="gross"
                                            name="Gross Revenue"
                                            stroke={dashboardPalette.revenueMetricColors.gross}
                                            strokeWidth={2}
                                            dot={false}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="premium"
                                            name="Premium Revenue"
                                            stroke={dashboardPalette.revenueMetricColors.premium}
                                            strokeWidth={2}
                                            dot={false}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </Box>
                        )}
                    </>
                )}
            </Box>
        </Box>
    );
};

export default RevenueOverviewSection;
