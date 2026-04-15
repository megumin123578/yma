import { Box, MenuItem, TextField, Typography } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import ChannelSwitcher, { CHANNEL_SWITCHER_SX } from "../ChannelSwitcher";
import {
    getSharedFilterControlSx,
    getSharedSelectMenuProps,
} from "../filterStyles";
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
    const theme = useTheme();
    const filterControlSx = getSharedFilterControlSx(theme);
    const selectMenuProps = getSharedSelectMenuProps(theme);

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
                    textFieldSx={filterControlSx}
                />

                <TextField
                    select
                    size="small"
                    label="Period"
                    value={overviewRange}
                    onChange={(e) => onOverviewRangeChange(e.target.value)}
                    sx={getSharedFilterControlSx(theme, {
                        ...CHANNEL_SWITCHER_SX,
                        minWidth: { xs: "100%", sm: 270 },
                        flex: "0 1 312px",
                        maxWidth: 356,
                    })}
                    SelectProps={{ MenuProps: selectMenuProps }}
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
