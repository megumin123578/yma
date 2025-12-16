import { Box } from "@mui/material"
import Header from "../../components/Header";
import ContentAnalytics from "../../components/Content";

const Dashboard = () => {
    return (
        <Box m="20px">
            <Header title="CONTENT" subtitle="Welcome to your content" />
            <Box mt={3}>
                <ContentAnalytics />
            </Box>
        </Box>
    );
};


export default Dashboard;
