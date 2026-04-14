import { useEffect, useState } from "react";
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { formatDuration } from "../Module";

const ContentVideoThumbnail = ({ src, videoId, alt, duration }) => {
    const theme = useTheme();
    const [currentSrc, setCurrentSrc] = useState(src);
    const [hasError, setHasError] = useState(false);

    useEffect(() => {
        setCurrentSrc(src);
        setHasError(false);
    }, [src]);

    const handleImgError = () => {
        if (videoId && currentSrc.includes("mqdefault")) {
            setCurrentSrc(`https://i.ytimg.com/vi/${videoId}/hqdefault.jpg`);
        } else if (videoId && currentSrc.includes("hqdefault")) {
            setCurrentSrc(`https://i.ytimg.com/vi/${videoId}/default.jpg`);
        } else {
            setHasError(true);
        }
    };

    if (hasError || !currentSrc) {
        return (
            <Box
                sx={{
                    width: 90,
                    aspectRatio: "16/9",
                    borderRadius: 1.5,
                    bgcolor:
                        theme.palette.mode === "dark"
                            ? "rgba(255,255,255,0.05)"
                            : "rgba(0,0,0,0.05)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "1px solid",
                    borderColor: theme.palette.divider,
                }}
            />
        );
    }

    return (
        <Box sx={{ position: "relative", display: "inline-flex" }}>
            <img
                src={currentSrc}
                width={90}
                style={{ borderRadius: 6 }}
                alt={alt || ""}
                onError={handleImgError}
            />
            {duration != null && (
                <Box
                    sx={{
                        position: "absolute",
                        right: 4,
                        bottom: 4,
                        px: 0.5,
                        py: 0.25,
                        borderRadius: 0.75,
                        fontSize: 11,
                        fontWeight: 600,
                        color: "#fff",
                        backgroundColor: "rgba(15,23,42,0.8)",
                    }}
                >
                    {formatDuration(duration)}
                </Box>
            )}
        </Box>
    );
};

export default ContentVideoThumbnail;
