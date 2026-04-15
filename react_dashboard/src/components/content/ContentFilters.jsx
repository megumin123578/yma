import dayjs from "dayjs";
import {
    Checkbox,
    FormControl,
    InputLabel,
    ListItemText,
    MenuItem,
    Select,
    Stack,
} from "@mui/material";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "../ChannelSwitcher";

const ContentFilters = ({
    hideChannelSwitcher,
    channelList,
    channelId,
    setChannelId,
    channelRevenueMap,
    showAllMode,
    setShowAllChannel,
    chartType,
    setChartType,
    period,
    setPeriod,
    contentPeriodOptions,
    selectedTableMetrics,
    setSelectedTableMetrics,
    tableMetricOptions,
    startDate,
    setStartDate,
    endDate,
    setEndDate,
}) => {
    return (
        <Stack direction="row" spacing={2} flexWrap="wrap">
            {!hideChannelSwitcher && (
                <ChannelSwitcher
                    options={channelList.map((channelOption) => ({
                        value: channelOption.id,
                        label: channelOption.title,
                        avatar: channelOption.avatar,
                    }))}
                    value={channelId}
                    onChange={(option) => setChannelId(option?.value || "")}
                    sx={CHANNEL_SWITCHER_SX}
                    getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
                    showAllDisabled={!channelList.length}
                    showAllVisible={false}
                    showAllActive={showAllMode}
                    showAllSelectedLabel="All channels"
                    onShowAllClick={setShowAllChannel}
                />
            )}

            <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel>Chart</InputLabel>
                <Select
                    value={chartType}
                    label="Chart"
                    onChange={(e) => setChartType(e.target.value)}
                >
                    <MenuItem value="bar">Bar</MenuItem>
                    <MenuItem value="line">Line</MenuItem>
                </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel>Period</InputLabel>
                <Select
                    value={period}
                    label="Period"
                    onChange={(e) => setPeriod(e.target.value)}
                >
                    {contentPeriodOptions.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                            {option.label}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 320 }}>
                <InputLabel>Table Metrics</InputLabel>
                <Select
                    multiple
                    value={selectedTableMetrics}
                    label="Table Metrics"
                    onChange={(e) => {
                        const rawValue =
                            typeof e.target.value === "string"
                                ? e.target.value.split(",")
                                : e.target.value;
                        const selected = new Set(rawValue);
                        const ordered = tableMetricOptions
                            .map((metric) => metric.value)
                            .filter((metricValue) => selected.has(metricValue));
                        setSelectedTableMetrics(ordered);
                    }}
                    renderValue={(selected) => `Metrics (${selected.length})`}
                >
                    {tableMetricOptions.map((metric) => (
                        <MenuItem key={metric.value} value={metric.value}>
                            <Checkbox
                                size="small"
                                checked={selectedTableMetrics.includes(metric.value)}
                            />
                            <ListItemText primary={metric.label} />
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {period === "custom" && (
                <LocalizationProvider dateAdapter={AdapterDayjs}>
                    <Stack direction="row" spacing={1}>
                        <DatePicker
                            label="Start"
                            value={startDate ? dayjs(startDate) : null}
                            onChange={(value) =>
                                setStartDate(value ? value.format("YYYY-MM-DD") : "")
                            }
                        />
                        <DatePicker
                            label="End"
                            value={endDate ? dayjs(endDate) : null}
                            onChange={(value) =>
                                setEndDate(value ? value.format("YYYY-MM-DD") : "")
                            }
                        />
                    </Stack>
                </LocalizationProvider>
            )}
        </Stack>
    );
};

export default ContentFilters;
