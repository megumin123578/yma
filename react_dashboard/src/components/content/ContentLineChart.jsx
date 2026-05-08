import { memo, useCallback, useMemo } from "react";
import dayjs from "dayjs";
import { ResponsiveLine } from "@nivo/line";

const ContentLineChart = memo(function ContentLineChart({
    data,
    margin,
    lineDateExtent,
    xTickValues,
    metric,
    themeMode,
    seriesColors,
    onSliceMove,
    onSliceLeave,
    formatMetricValue,
}) {
    const isDark = themeMode === "dark";
    const axisTextColor = isDark ? "#e5e7eb" : "#374151";
    const spansMultipleYears = useMemo(() => {
        const minYear = dayjs(lineDateExtent?.min).year();
        const maxYear = dayjs(lineDateExtent?.max).year();
        return Number.isFinite(minYear) && Number.isFinite(maxYear) && minYear !== maxYear;
    }, [lineDateExtent]);

    const colorFn = useCallback(
        (serie) => seriesColors[serie.id] || "#60a5fa",
        [seriesColors]
    );

    const renderBottomTick = useCallback(
        (tick) => {
            const date = tick.value instanceof Date ? tick.value : new Date(tick.value);
            const label = dayjs(date).format(spansMultipleYears ? "DD/MM/YY" : "DD/MM");

            return (
                <g
                    transform={`translate(${tick.x},${tick.y})`}
                    style={{ pointerEvents: "none" }}
                >
                    <text
                        y={6}
                        textAnchor="middle"
                        dominantBaseline="hanging"
                        style={{
                            fill: axisTextColor,
                            fontSize: 11,
                            fontWeight: 600,
                        }}
                    >
                        {label}
                    </text>
                </g>
            );
        },
        [axisTextColor, spansMultipleYears]
    );

    const axisBottom = useMemo(
        () => ({
            tickValues: xTickValues,
            tickSize: 0,
            tickPadding: 10,
            renderTick: renderBottomTick,
        }),
        [xTickValues, renderBottomTick]
    );

    const axisLeft = useMemo(
        () => ({
            tickSize: 0,
            tickPadding: 8,
            format: (value) => formatMetricValue(metric, value),
        }),
        [formatMetricValue, metric]
    );

    const nivoTheme = useMemo(
        () => ({
            axis: {
                ticks: {
                    text: {
                        fill: axisTextColor,
                        fontSize: 11,
                        fontWeight: 600,
                    },
                    line: {
                        stroke: isDark
                            ? "rgba(148,163,184,0.4)"
                            : "rgba(148,163,184,0.6)",
                    },
                },
                legend: {
                    text: { fill: axisTextColor },
                },
            },
            grid: {
                line: {
                    stroke: isDark
                        ? "rgba(148,163,184,0.18)"
                        : "rgba(148,163,184,0.25)",
                    strokeWidth: 1,
                    strokeDasharray: "4 4",
                },
            },
            crosshair: {
                line: {
                    stroke: isDark
                        ? "rgba(226,232,240,0.45)"
                        : "rgba(15,23,42,0.35)",
                    strokeWidth: 1,
                    strokeDasharray: "3 3",
                },
            },
            tooltip: {
                container: {
                    background: "transparent",
                    padding: 0,
                    boxShadow: "none",
                    border: "none",
                    borderRadius: 0,
                },
            },
        }),
        [axisTextColor, isDark]
    );

    return (
        <ResponsiveLine
            debounceResize={150}
            data={data}
            margin={margin}
            animate={false}
            xScale={{
                type: "time",
                format: "native",
                useUTC: false,
                precision: "day",
                min: lineDateExtent.min,
                max: lineDateExtent.max,
            }}
            yScale={{ type: "linear", min: 0, stacked: false }}
            curve="linear"
            enablePoints={true}
            pointSize={6}
            colors={colorFn}
            enableSlices="x"
            enableCrosshair
            crosshairType="cross"
            tooltip={() => null}
            sliceTooltip={() => null}
            onMouseMove={onSliceMove}
            onMouseLeave={onSliceLeave}
            axisBottom={axisBottom}
            axisLeft={axisLeft}
            theme={nivoTheme}
        />
    );
});

ContentLineChart.displayName = "ContentLineChart";

export default ContentLineChart;
