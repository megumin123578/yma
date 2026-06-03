// components/research/Markdown.jsx — render markdown (GFM) theo theme MUI.
import { Box, useTheme } from "@mui/material";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const Markdown = ({ text }) => {
  const theme = useTheme();
  if (!text || !String(text).trim()) return null;
  const codeBg =
    theme.palette.mode === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
  return (
    <Box
      sx={{
        lineHeight: 1.7,
        fontSize: "0.95rem",
        color: theme.palette.text.primary,
        wordBreak: "break-word",
        "& h1": { fontSize: "1.4rem", fontWeight: 800, mt: 2, mb: 1 },
        "& h2": {
          fontSize: "1.15rem",
          fontWeight: 800,
          mt: 2.5,
          mb: 1,
          pb: 0.5,
          borderBottom: `1px solid ${theme.palette.divider}`,
        },
        "& h3": { fontSize: "1.02rem", fontWeight: 700, mt: 2, mb: 0.75 },
        "& p": { my: 1 },
        "& ul, & ol": { pl: 3, my: 1 },
        "& li": { mb: 0.5 },
        "& strong": { fontWeight: 700 },
        "& a": { color: theme.palette.primary.main },
        "& blockquote": {
          borderLeft: `3px solid ${theme.palette.primary.main}`,
          pl: 1.5,
          ml: 0,
          my: 1.5,
          color: theme.palette.text.secondary,
          fontStyle: "italic",
        },
        "& hr": {
          border: "none",
          borderTop: `1px solid ${theme.palette.divider}`,
          my: 2,
        },
        "& code": {
          bgcolor: codeBg,
          px: 0.6,
          py: 0.2,
          borderRadius: 1,
          fontSize: "0.85em",
        },
        "& pre": {
          bgcolor: codeBg,
          p: 1.5,
          borderRadius: 2,
          overflow: "auto",
        },
        "& pre code": { bgcolor: "transparent", p: 0 },
        "& table": {
          borderCollapse: "collapse",
          width: "100%",
          my: 1.5,
          fontSize: "0.9rem",
        },
        "& th, & td": {
          border: `1px solid ${theme.palette.divider}`,
          p: 0.75,
          textAlign: "left",
        },
        "& th": { fontWeight: 700, bgcolor: theme.palette.background.default },
      }}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </Box>
  );
};

export default Markdown;
