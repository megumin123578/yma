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
import { alpha, useTheme } from "@mui/material/styles";
import { LocalizationProvider, DatePicker } from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "../ChannelSwitcher";
import {
    getSharedDatePickerSlotProps,
    getSharedFilterControlSx,
    getSharedSelectMenuProps,
} from "../filterStyles";

const hasLocalizationProvider = typeof LocalizationProvider === "function";
const hasDatePicker = typeof DatePicker === "function" || (typeof DatePicker === "object" && DatePicker !== null);

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
    leadingFilters,
}) => {
    const theme = useTheme();
    const isDark = theme.palette.mode === "dark";
    const filterControlSx = getSharedFilterControlSx(theme);
    const selectMenuProps = getSharedSelectMenuProps(theme);
    const datePickerSlotProps = getSharedDatePickerSlotProps(theme);

    return (
        <Stack
            direction={{ xs: "column", md: "row" }}
            spacing={{ xs: 1.25, sm: 1.5, md: 2 }}
            useFlexGap
            flexWrap="wrap"
            sx={{
                mt: 0.5,
                alignItems: { xs: "stretch", md: "center" },
            }}
        >
            {leadingFilters}
            {!hideChannelSwitcher && (
                <ChannelSwitcher
                    options={channelList.map((channelOption) => ({
                        value: channelOption.id,
                        label: channelOption.title,
                        avatar: channelOption.avatar,
                    }))}
                    value={channelId}
                    onChange={(option) => setChannelId(option?.value || "")}
                    getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
                    showAllDisabled={!channelList.length}
                    showAllVisible={false}
                    showAllActive={showAllMode}
                    showAllSelectedLabel="All channels"
                    onShowAllClick={setShowAllChannel}
                    sx={{
                        ...CHANNEL_SWITCHER_SX,
                        minWidth: { xs: "100%", md: 280 },
                        maxWidth: { xs: "100%", md: 380 },
                        flex: { xs: "1 1 100%", md: "1 1 320px" },
                    }}
                    textFieldSx={filterControlSx}
                />
            )}

            <FormControl size="small" sx={filterControlSx}>
                <InputLabel>Chart</InputLabel>
                <Select
                    value={chartType}
                    label="Chart"
                    onChange={(e) => setChartType(e.target.value)}
                    MenuProps={selectMenuProps}
                >
                    <MenuItem value="bar">Bar</MenuItem>
                    <MenuItem value="line">Line</MenuItem>
                </Select>
            </FormControl>

            <FormControl
                size="small"
                sx={{
                    ...filterControlSx,
                    flex: { xs: "1 1 100%", sm: "1 1 220px" },
                }}
            >
                <InputLabel>Period</InputLabel>
                <Select
                    value={period}
                    label="Period"
                    onChange={(e) => setPeriod(e.target.value)}
                    MenuProps={selectMenuProps}
                >
                    {contentPeriodOptions.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                            {option.label}
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl
                size="small"
                sx={{
                    ...filterControlSx,
                    flex: { xs: "1 1 100%", lg: "1 1 320px" },
                }}
            >
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
                    MenuProps={selectMenuProps}
                >
                    {tableMetricOptions.map((metric) => (
                        <MenuItem key={metric.value} value={metric.value}>
                            <Checkbox
                                size="small"
                                checked={selectedTableMetrics.includes(metric.value)}
                                sx={{
                                    color: isDark ? alpha("#60a5fa", 0.9) : alpha("#2563eb", 0.78),
                                    "&.Mui-checked": {
                                        color: isDark ? "#60a5fa" : "#2563eb",
                                    },
                                }}
                            />
                            <ListItemText primary={metric.label} />
                        </MenuItem>
                    ))}
                </Select>
            </FormControl>

            {period === "custom" && hasLocalizationProvider && hasDatePicker && (
                <LocalizationProvider dateAdapter={AdapterDayjs}>
                    <Stack
                        direction={{ xs: "column", sm: "row" }}
                        spacing={1}
                        sx={{
                            width: { xs: "100%", lg: "auto" },
                            flex: { xs: "1 1 100%", lg: "0 0 auto" },
                        }}
                    >
                        <DatePicker
                            label="Start"
                            value={startDate ? dayjs(startDate) : null}
                            onChange={(value) =>
                                setStartDate(value ? value.format("YYYY-MM-DD") : "")
                            }
                            slotProps={datePickerSlotProps}
                        />
                        <DatePicker
                            label="End"
                            value={endDate ? dayjs(endDate) : null}
                            onChange={(value) =>
                                setEndDate(value ? value.format("YYYY-MM-DD") : "")
                            }
                            slotProps={datePickerSlotProps}
                        />
                    </Stack>
                </LocalizationProvider>
            )}
        </Stack>
    );
};

export default ContentFilters;
