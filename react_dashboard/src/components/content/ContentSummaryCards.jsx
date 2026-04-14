import { Box, Paper, Typography, useTheme } from "@mui/material";

const ContentSummaryCards = ({ items }) => {
    const theme = useTheme();

    if (!items?.length) return null;

    return (
        <Box
            sx={{
                display: "grid",
                gridTemplateColumns: {
                    xs: "repeat(2, minmax(0, 1fr))",
                    md: "repeat(3, minmax(0, 1fr))",
                    xl: "repeat(6, minmax(0, 1fr))",
                },
                gap: 1.5,
            }}
        >
            {items.map((item) => (
                <Paper
                    key={item.label}
                    elevation={0}
                    sx={{
                        p: 1.75,
                        borderRadius: 2.5,
                        border: "1px solid",
                        borderColor:
                            theme.palette.mode === "dark"
                                ? "rgba(148,163,184,0.2)"
                                : "rgba(15,23,42,0.1)",
                        background:
                            theme.palette.mode === "dark"
                                ? "linear-gradient(180deg, rgba(15,23,42,0.88), rgba(10,15,24,0.78))"
                                : "linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.95))",
                    }}
                >
                    <Typography
                        variant="caption"
                        sx={{
                            display: "block",
                            mb: 0.6,
                            letterSpacing: "0.08em",
                            textTransform: "uppercase",
                            color: "text.secondary",
                            fontWeight: 700,
                        }}
                    >
                        {item.label}
                    </Typography>
                    <Typography
                        variant="h6"
                        sx={{
                            fontWeight: 800,
                            color: "text.primary",
                        }}
                    >
                        {item.value}
                    </Typography>
                </Paper>
            ))}
        </Box>
    );
};

export default ContentSummaryCards;
