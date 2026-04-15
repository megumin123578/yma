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
    const theme = useTheme();
    const isDark = theme.palette.mode === "dark";
    const accentColor = isDark ? theme.palette.info.light : theme.palette.primary.main;

    const filterControlSx = {
        minWidth: { xs: "100%", sm: 160 },
        flex: { xs: "1 1 100%", sm: "1 1 180px" },
        "& .MuiInputLabel-root": {
            fontWeight: 700,
            color: isDark ? alpha("#cbd5e1", 0.78) : alpha("#334155", 0.72),
        },
        "& .MuiInputLabel-root.Mui-focused": {
            color: accentColor,
        },
        "& .MuiInputLabel-root.MuiFormLabel-filled": {
            color: isDark ? alpha("#e2e8f0", 0.88) : alpha("#0f172a", 0.76),
        },
        "& .MuiInputLabel-root.MuiInputLabel-shrink": {
            color: isDark ? alpha("#e2e8f0", 0.88) : alpha("#0f172a", 0.76),
        },
        "& .MuiOutlinedInput-root, & .MuiPickersOutlinedInput-root": {
            borderRadius: 3,
            minHeight: 46,
            backgroundColor: isDark ? alpha("#0f172a", 0.78) : alpha("#ffffff", 0.94),
            boxShadow: isDark
                ? `0 10px 24px ${alpha("#020617", 0.22)}`
                : `0 10px 24px ${alpha("#cbd5e1", 0.2)}`,
            transition: "border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease",
            "& fieldset": {
                borderColor: isDark ? alpha("#94a3b8", 0.28) : alpha("#0f172a", 0.1),
            },
            "&:hover fieldset": {
                borderColor: alpha(accentColor, isDark ? 0.7 : 0.42),
            },
            "&.Mui-focused": {
                backgroundColor: isDark ? alpha("#0f172a", 0.9) : "#ffffff",
                boxShadow: `0 0 0 3px ${alpha(accentColor, isDark ? 0.2 : 0.14)}`,
            },
            "&.Mui-focused fieldset": {
                borderColor: accentColor,
            },
            "& .MuiSelect-select": {
                color: isDark ? "#e2e8f0" : "#0f172a",
            },
            "& input, & .MuiPickersSectionList-root": {
                color: isDark ? "#e2e8f0" : "#0f172a",
            },
            "& .MuiSvgIcon-root": {
                color: isDark ? alpha("#cbd5e1", 0.88) : alpha("#334155", 0.72),
            },
        },
        "& .MuiPickersInputBase-root": {
            borderRadius: 3,
            minHeight: 46,
            backgroundColor: isDark ? alpha("#0f172a", 0.78) : alpha("#ffffff", 0.94),
            boxShadow: isDark
                ? `0 10px 24px ${alpha("#020617", 0.22)}`
                : `0 10px 24px ${alpha("#cbd5e1", 0.2)}`,
        },
        "& .MuiPickersOutlinedInput-notchedOutline": {
            borderColor: isDark ? alpha("#94a3b8", 0.28) : alpha("#0f172a", 0.1),
        },
        "&:hover .MuiPickersOutlinedInput-notchedOutline": {
            borderColor: alpha(accentColor, isDark ? 0.7 : 0.42),
        },
        "& .MuiPickersInputBase-root.Mui-focused": {
            backgroundColor: isDark ? alpha("#0f172a", 0.9) : "#ffffff",
            boxShadow: `0 0 0 3px ${alpha(accentColor, isDark ? 0.2 : 0.14)}`,
        },
        "& .MuiPickersInputBase-root.Mui-focused .MuiPickersOutlinedInput-notchedOutline": {
            borderColor: `${accentColor} !important`,
        },
        "& .MuiPickersSectionList-root": {
            padding: "10px 14px",
        },
        "& .MuiPickersInputAdornment-root .MuiButtonBase-root": {
            color: isDark ? alpha("#cbd5e1", 0.88) : alpha("#334155", 0.72),
        },
    };

    const selectMenuProps = {
        PaperProps: {
            sx: {
                mt: 1,
                borderRadius: 3,
                border: `1px solid ${isDark ? alpha("#94a3b8", 0.22) : alpha("#0f172a", 0.08)}`,
                background: isDark
                    ? "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(15,23,42,0.94))"
                    : "linear-gradient(180deg, rgba(255,255,255,0.99), rgba(248,250,252,0.98))",
                boxShadow: isDark
                    ? "0 20px 44px rgba(2,6,23,0.5)"
                    : "0 18px 38px rgba(15,23,42,0.14)",
                "& .MuiMenuItem-root": {
                    minHeight: 42,
                    borderRadius: 2,
                    mx: 0.75,
                    my: 0.25,
                },
                "& .MuiMenuItem-root.Mui-selected": {
                    backgroundColor: alpha(accentColor, isDark ? 0.18 : 0.1),
                },
                "& .MuiMenuItem-root.Mui-selected:hover": {
                    backgroundColor: alpha(accentColor, isDark ? 0.24 : 0.14),
                },
            },
        },
        MenuListProps: {
            dense: true,
            sx: {
                py: 0.75,
            },
        },
    };

    const datePickerSlotProps = {
        textField: {
            size: "small",
            fullWidth: true,
            sx: {
                ...filterControlSx,
                minWidth: { xs: "100%", sm: 170 },
            },
        },
        popper: {
            sx: {
                "& .MuiPaper-root": {
                    mt: 1,
                    borderRadius: 3,
                    border: `1px solid ${isDark ? alpha("#94a3b8", 0.22) : alpha("#0f172a", 0.08)}`,
                    background: isDark
                        ? "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(15,23,42,0.94))"
                        : "linear-gradient(180deg, rgba(255,255,255,0.99), rgba(248,250,252,0.98))",
                    boxShadow: isDark
                        ? "0 20px 44px rgba(2,6,23,0.5)"
                        : "0 18px 38px rgba(15,23,42,0.14)",
                },
                "& .MuiPickersCalendarHeader-root": {
                    px: 2,
                    pt: 1.5,
                },
                "& .MuiPickersCalendarHeader-label": {
                    fontWeight: 800,
                    color: isDark ? "#e2e8f0" : "#0f172a",
                },
                "& .MuiDayCalendar-weekDayLabel": {
                    color: isDark ? alpha("#cbd5e1", 0.76) : alpha("#334155", 0.72),
                    fontWeight: 700,
                },
                "& .MuiPickersDay-root": {
                    color: isDark ? "#e2e8f0" : "#0f172a",
                    borderRadius: 2,
                },
                "& .MuiPickersDay-root:hover": {
                    backgroundColor: alpha(accentColor, isDark ? 0.16 : 0.1),
                },
                "& .MuiPickersDay-root.Mui-selected": {
                    backgroundColor: accentColor,
                    color: isDark ? "#082f49" : "#ffffff",
                },
                "& .MuiPickersDay-root.Mui-selected:hover": {
                    backgroundColor: accentColor,
                },
                "& .MuiPickersArrowSwitcher-button, & .MuiPickersCalendarHeader-switchViewButton": {
                    color: isDark ? alpha("#cbd5e1", 0.88) : alpha("#334155", 0.8),
                },
            },
        },
        mobilePaper: {
            sx: {
                borderRadius: 3,
                border: `1px solid ${isDark ? alpha("#94a3b8", 0.22) : alpha("#0f172a", 0.08)}`,
                background: isDark
                    ? "linear-gradient(180deg, rgba(15,23,42,0.98), rgba(15,23,42,0.94))"
                    : "linear-gradient(180deg, rgba(255,255,255,0.99), rgba(248,250,252,0.98))",
                boxShadow: isDark
                    ? "0 20px 44px rgba(2,6,23,0.5)"
                    : "0 18px 38px rgba(15,23,42,0.14)",
            },
        },
    };

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

            {period === "custom" && (
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
