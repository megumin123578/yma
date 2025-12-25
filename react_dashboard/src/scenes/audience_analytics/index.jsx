import { Box } from "@mui/material";
import Header from "../../components/Header";
import AudienceAnalytics from "../../components/AudienceAnalytics";

const AudienceAnalyticsScene = () => {
  return (
    <Box m="20px">
      <Header title="Audience Analytics" subtitle="Demographics and retention insights" />
      <AudienceAnalytics />
    </Box>
  );
};

export default AudienceAnalyticsScene;
