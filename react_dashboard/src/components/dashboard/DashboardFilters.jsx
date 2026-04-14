import { Box, MenuItem, TextField, Typography } from "@mui/material";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "../ChannelSwitcher";
import { OVERVIEW_RANGES } from "./dashboardUtils";

const DashboardFilters = ({
    channels,
    selectedChannel,
    onChannelChange,
    channelAvatarMap,
    channelRevenueMap,
    loadingChannels,
    overviewRange,
    onOverviewRangeChange,
    totalVideos,
    colors,
}) => {
    return (
        <Box
            mb={2}
            display="flex"
            alignItems={{ xs: "stretch", md: "center" }}
            justifyContent="space-between"
            flexWrap="wrap"
            gap={2}
        >
            <Box
                display="flex"
                alignItems={{ xs: "stretch", sm: "center" }}
                gap={2}
                flexWrap="wrap"
                sx={{ width: { xs: "100%", lg: "auto" }, flex: "1 1 520px" }}
            >
                <ChannelSwitcher
                    options={channels}
                    value={selectedChannel}
                    onChange={(option) => onChannelChange(option?.value || "")}
                    sx={CHANNEL_SWITCHER_SX}
                    disabled={loadingChannels}
                    placeholder={loadingChannels ? "Loading channels..." : "Search by channel name"}
                    noOptionsText={loadingChannels ? "Loading channels..." : "No channels found"}
                    getOptionAvatar={(option) => channelAvatarMap[option?.value] || ""}
                    getOptionMeta={(option) => channelRevenueMap[option?.value] || ""}
                />

                <TextField
                    select
                    size="small"
                    label="Date range"
                    value={overviewRange}
                    onChange={(e) => onOverviewRangeChange(e.target.value)}
                    sx={{ minWidth: { xs: "100%", sm: 160 } }}
                >
                    {OVERVIEW_RANGES.map((range) => (
                        <MenuItem key={range.value} value={range.value}>
                            {range.label}
                        </MenuItem>
                    ))}
                </TextField>
            </Box>

            {totalVideos > 0 && (
                <Typography variant="body2" color={colors.grey[300]}>
                    Total: <span style={{ fontWeight: 600 }}>{totalVideos} video</span>
                </Typography>
            )}
        </Box>
    );
};

export default DashboardFilters;
