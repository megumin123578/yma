import { Box } from "@mui/material";
import Header from "../../components/Header";
import ReachAnalytics from "../../components/ReachAnalytics";

const ReachAnalyticsScene = () => {
  return (
    <Box m="20px">
      <Header title="Reach" subtitle="Impressions and click-through metrics" />
      <ReachAnalytics />
    </Box>
  );
};

export default ReachAnalyticsScene;
