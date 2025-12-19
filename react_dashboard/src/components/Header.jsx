import { Typography, Box, useTheme } from "@mui/material";
import { tokens } from "../theme";

const Header = ({ title, subtitle}) => {
    const theme = useTheme();
    const colors = tokens(theme.palette.mode);

    return (<Box mb = "30px">
        <Typography
        variant = 'h2'
        color = {colors.grey[100]}
        fontWeight = 'bold'
        sx = {{
            m: "0 0 5px 0",
            textShadow:
              "0 0 6px rgba(144,202,249,0.55), 0 0 18px rgba(144,202,249,0.35)",
            animation:
              "headerFloat 4s ease-in-out infinite, headerGlow 2.8s ease-in-out infinite, headerOutline 3.4s linear infinite",
            "@keyframes headerFloat": {
                "0%": { transform: "translateY(0)" },
                "50%": { transform: "translateY(-4px)" },
                "100%": { transform: "translateY(0)" },
            },
            "@keyframes headerGlow": {
              "0%": { textShadow: "0 0 4px rgba(144,202,249,0.4), 0 0 10px rgba(144,202,249,0.25)" },
              "50%": { textShadow: "0 0 10px rgba(144,202,249,0.85), 0 0 22px rgba(144,202,249,0.55)" },
              "100%": { textShadow: "0 0 4px rgba(144,202,249,0.4), 0 0 10px rgba(144,202,249,0.25)" },
            },
            "@keyframes headerOutline": {
              "0%": { textShadow: "1px 0 0 rgba(144,202,249,0.9), 0 0 8px rgba(144,202,249,0.5)" },
              "25%": { textShadow: "0 1px 0 rgba(144,202,249,0.9), 0 0 10px rgba(144,202,249,0.55)" },
              "50%": { textShadow: "-1px 0 0 rgba(144,202,249,0.9), 0 0 8px rgba(144,202,249,0.5)" },
              "75%": { textShadow: "0 -1px 0 rgba(144,202,249,0.9), 0 0 10px rgba(144,202,249,0.55)" },
              "100%": { textShadow: "1px 0 0 rgba(144,202,249,0.9), 0 0 8px rgba(144,202,249,0.5)" },
            },
        }}
        >
            {title}
        </Typography>

        <Typography
        variant = 'h5'
        color = {colors.greenAccent[400]}
        sx={{
            textShadow:
              "0 0 6px rgba(76,206,172,0.5), 0 0 16px rgba(76,206,172,0.3)",
            animation:
              "headerFloatSub 4.5s ease-in-out infinite, headerGlowSub 3.2s ease-in-out infinite, headerOutlineSub 3.8s linear infinite",
            "@keyframes headerFloatSub": {
                "0%": { transform: "translateY(0)" },
                "50%": { transform: "translateY(-3px)" },
                "100%": { transform: "translateY(0)" },
            },
            "@keyframes headerGlowSub": {
              "0%": { textShadow: "0 0 4px rgba(76,206,172,0.35), 0 0 10px rgba(76,206,172,0.2)" },
              "50%": { textShadow: "0 0 10px rgba(76,206,172,0.75), 0 0 20px rgba(76,206,172,0.5)" },
              "100%": { textShadow: "0 0 4px rgba(76,206,172,0.35), 0 0 10px rgba(76,206,172,0.2)" },
            },
            "@keyframes headerOutlineSub": {
              "0%": { textShadow: "1px 0 0 rgba(76,206,172,0.85), 0 0 7px rgba(76,206,172,0.45)" },
              "25%": { textShadow: "0 1px 0 rgba(76,206,172,0.85), 0 0 9px rgba(76,206,172,0.5)" },
              "50%": { textShadow: "-1px 0 0 rgba(76,206,172,0.85), 0 0 7px rgba(76,206,172,0.45)" },
              "75%": { textShadow: "0 -1px 0 rgba(76,206,172,0.85), 0 0 9px rgba(76,206,172,0.5)" },
              "100%": { textShadow: "1px 0 0 rgba(76,206,172,0.85), 0 0 7px rgba(76,206,172,0.45)" },
            },
        }}
        >
            {subtitle}
        </Typography>
    </Box>
    )
}
export default Header
