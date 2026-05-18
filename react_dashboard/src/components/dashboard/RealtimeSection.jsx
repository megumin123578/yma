import { Box, Stack, Typography } from "@mui/material";
import {
    Bar,
    BarChart,
    CartesianGrid,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from "recharts";
import { formatNumber } from "./dashboardUtils";

const formatHourTick = (value) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    const hour = d.getHours().toString().padStart(2, "0");
    return `${hour}:00`;
};

const formatMinuteTick = (value) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    const hour = d.getHours().toString().padStart(2, "0");
    const minute = d.getMinutes().toString().padStart(2, "0");
    return `${hour}:${minute}`;
};

const formatHourLabel = (value) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    const day = d.getDate().toString().padStart(2, "0");
    const month = (d.getMonth() + 1).toString().padStart(2, "0");
    const hour = d.getHours().toString().padStart(2, "0");
    return `${day}/${month} ${hour}:00`;
};

const formatMinuteLabel = (value) => {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    const hour = d.getHours().toString().padStart(2, "0");
    const minute = d.getMinutes().toString().padStart(2, "0");
    return `${hour}:${minute}`;
};

const computeTicks = (rows, count) => {
    if (!rows.length) return [];
    if (rows.length <= count) return rows.map((row) => row.bucket);
    const result = [];
    const step = (rows.length - 1) / (count - 1);
    for (let i = 0; i < count; i += 1) {
        const idx = Math.round(i * step);
        result.push(rows[idx]?.bucket);
    }
    return Array.from(new Set(result.filter(Boolean)));
};

const RealtimePanel = ({
    title,
    subtitle,
    rows,
    totals,
    color,
    tickFormatter,
    labelFormatter,
    tickCount,
    sectionSx,
    chartCardSx,
    chartTooltipStyles,
    emptyMessage,
}) => {
    const totalViews = totals?.views ?? 0;
    const ticks = computeTicks(rows, tickCount);

    return (
        <Box sx={{ ...sectionSx, p: 3, display: "flex", flexDirection: "column" }}>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={1}>
                <Box>
                    <Typography variant="subtitle1" fontWeight={700}>
                        {title}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        {subtitle}
                    </Typography>
                </Box>
                <Box textAlign="right">
                    <Typography variant="caption" color="text.secondary">
                        Views
                    </Typography>
                    <Typography variant="h5" fontWeight={700} sx={{ color }}>
                        {formatNumber(totalViews)}
                    </Typography>
                </Box>
            </Stack>
            {rows.length === 0 ? (
                <Box
                    sx={{
                        flex: 1,
                        minHeight: 220,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    <Typography variant="body2" color="text.secondary">
                        {emptyMessage}
                    </Typography>
                </Box>
            ) : (
                <Box sx={{ ...chartCardSx, p: 1, width: "100%" }}>
                    <ResponsiveContainer width="100%" height={220}>
                        <BarChart
                            data={rows}
                            margin={{ top: 8, right: 8, left: -20, bottom: -6 }}
                        >
                            <CartesianGrid
                                stroke="rgba(148,163,184,0.2)"
                                strokeDasharray="3 3"
                            />
                            <XAxis
                                dataKey="bucket"
                                tick={{ fontSize: 11 }}
                                ticks={ticks}
                                tickFormatter={tickFormatter}
                                allowDuplicatedCategory={false}
                            />
                            <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
                            <Tooltip
                                {...chartTooltipStyles}
                                labelFormatter={labelFormatter}
                                formatter={(value, key) => [
                                    formatNumber(Number(value) || 0),
                                    key === "subscribers" ? "Subscribers" : "Views",
                                ]}
                            />
                            <Bar
                                dataKey="views"
                                fill={color}
                                radius={[4, 4, 0, 0]}
                                isAnimationActive={false}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                </Box>
            )}
        </Box>
    );
};

const RealtimeSection = ({
    sectionSx,
    chartCardSx,
    chartTooltipStyles,
    dashboardPalette,
    realtime48h,
    realtime60m,
}) => {
    return (
        <Box
            mt={2}
            sx={{
                display: "grid",
                gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
                gap: 2,
                width: "100%",
            }}
        >
            <RealtimePanel
                title="Realtime · Last 48 hours"
                subtitle="Views per hour"
                rows={realtime48h?.rows || []}
                totals={realtime48h?.totals || {}}
                color={dashboardPalette.accentAlt}
                tickFormatter={formatHourTick}
                labelFormatter={formatHourLabel}
                tickCount={6}
                sectionSx={sectionSx}
                chartCardSx={chartCardSx}
                chartTooltipStyles={chartTooltipStyles}
                emptyMessage="Waiting for live counter snapshots..."
            />
            <RealtimePanel
                title="Realtime · Last 60 minutes"
                subtitle="Views per minute"
                rows={realtime60m?.rows || []}
                totals={realtime60m?.totals || {}}
                color={dashboardPalette.positive}
                tickFormatter={formatMinuteTick}
                labelFormatter={formatMinuteLabel}
                tickCount={6}
                sectionSx={sectionSx}
                chartCardSx={chartCardSx}
                chartTooltipStyles={chartTooltipStyles}
                emptyMessage="Waiting for live counter snapshots..."
            />
        </Box>
    );
};

export default RealtimeSection;
