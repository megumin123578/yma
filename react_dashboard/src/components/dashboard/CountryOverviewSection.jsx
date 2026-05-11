import { alpha } from "@mui/material/styles";
import { Box, Stack, Typography, useTheme } from "@mui/material";
import { ResponsiveChoropleth } from "@nivo/geo";
import { formatNumber } from "./dashboardUtils";

const CountryOverviewSection = ({
    rangeLabel,
    sectionSx,
    countryViews,
    countryMapData,
    countryDomainMax,
    countryResolvers,
    topCountries,
    dashboardPalette,
    geoFeatures,
}) => {
    const theme = useTheme();

    return (
        <Box sx={{ ...sectionSx, p: 3 }}>
            <Typography variant="subtitle1" fontWeight={700} mb={1}>
                Views by country ({rangeLabel})
            </Typography>
            {countryViews.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                    No data
                </Typography>
            ) : (
                <>
                    <Box height={240}>
                        <ResponsiveChoropleth
                            debounceResize={150}
                            data={countryMapData}
                            features={geoFeatures?.features || []}
                            valueFormat={formatNumber}
                            domain={[0, countryDomainMax]}
                            tooltip={({ feature }) => {
                                const label = countryResolvers.nameOf(feature.id);
                                const value = feature.value || 0;

                                return (
                                    <Box
                                        sx={{
                                            px: 1.2,
                                            py: 0.75,
                                            borderRadius: 1,
                                            fontSize: 13,
                                            fontWeight: 600,
                                            bgcolor:
                                                theme.palette.mode === "dark"
                                                    ? alpha(dashboardPalette.black, 0.75)
                                                    : dashboardPalette.surfaceStrong,
                                            boxShadow: 3,
                                        }}
                                    >
                                        <div>{label}</div>
                                        <div>Views: {formatNumber(value)}</div>
                                    </Box>
                                );
                            }}
                            unknownColor={theme.palette.action.disabled}
                            projectionScale={80}
                            projectionTranslation={[0.5, 0.65]}
                            borderWidth={1}
                            borderColor={dashboardPalette.white}
                        />
                    </Box>
                    <Box mt={2}>
                        <Stack>
                            {topCountries.map((row) => {
                                const pct =
                                    countryDomainMax > 0
                                        ? Math.max(
                                              6,
                                              Math.round((row.value / countryDomainMax) * 100)
                                          )
                                        : 0;

                                return (
                                    <Box key={row.id}>
                                        <Box display="flex" justifyContent="space-between" mb={0.5}>
                                            <Typography variant="body2">
                                                {countryResolvers.nameOf(row.id)}
                                            </Typography>
                                            <Typography variant="body2" fontWeight={600}>
                                                {formatNumber(row.value)}
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
                                                    width: `${pct}%`,
                                                    height: "100%",
                                                    borderRadius: 999,
                                                    background:
                                                        theme.palette.mode === "dark"
                                                            ? `linear-gradient(90deg, ${dashboardPalette.info}, ${dashboardPalette.accentSoft})`
                                                            : `linear-gradient(90deg, ${dashboardPalette.info}, ${dashboardPalette.accentAlt})`,
                                                }}
                                            />
                                        </Box>
                                    </Box>
                                );
                            })}
                        </Stack>
                    </Box>
                </>
            )}
        </Box>
    );
};

export default CountryOverviewSection;
