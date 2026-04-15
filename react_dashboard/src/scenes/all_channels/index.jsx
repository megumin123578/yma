import { Box } from "@mui/material";
import Header from "../../components/Header";
import ContentAnalytics from "../../components/content/ContentContainer";

const CONTENT_ALL_CHANNELS_VALUE = "__all__";

const AllChannelsScene = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="ALL CHANNELS" subtitle="Cross-channel content overview" />
      <Box mt={3}>
        <ContentAnalytics
          hideChannelSwitcher
          forcedChannelId={CONTENT_ALL_CHANNELS_VALUE}
        />
      </Box>
    </Box>
  );
};

export default AllChannelsScene;
