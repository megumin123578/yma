import { Box } from "@mui/material";
import Header from "../../components/Header";
import GeographyChart from "../../components/Geography";

const GeographyScene = () => {
    return (
        <Box m="20px">
            <Header title="Geography" subtitle="Audience distribution by country" />
            <GeographyChart />
        </Box>
    );
};

export default GeographyScene;
