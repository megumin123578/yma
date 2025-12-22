import { Box } from "@mui/material";
import Header from "../../components/Header";
import SmmstoreAnalytics from "../../components/SmmstoreAnalytics";

const SmmstoreAnalyticsScene = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="SMMStore Analytics" subtitle="Manage how much money spent last month" />
      <SmmstoreAnalytics />
    </Box>
  );
};

export default SmmstoreAnalyticsScene;
