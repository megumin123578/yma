import { Box } from "@mui/material"
import Header from "../../components/Header";
import ContentAnalytics from "../../components/content/ContentContainer";

const Dashboard = () => {
    return (
        <Box mx="20px" mt="0" mb="20px">
            <Header title="CONTENT" subtitle="Welcome to your content" />
            <Box mt={3}>
                <ContentAnalytics />
            </Box>
        </Box>
    );
};


export default Dashboard;
