import { Box } from "@mui/material";
import Header from "../../components/Header";
import RevenueAnalytics from "../../components/Revenue";

const RevenueAnalyticsScene = () => {
  return (
    <Box m="20px">
      <Header title="Revenue" subtitle="Monetization metrics over time" />
      <RevenueAnalytics />
    </Box>
  );
};

export default RevenueAnalyticsScene;
