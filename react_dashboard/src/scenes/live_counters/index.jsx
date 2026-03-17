import { Box } from "@mui/material";
import Header from "../../components/Header";
import LiveCounters from "../../components/LiveCounters";

const LiveCountersScene = () => {
  return (
    <Box m="20px">
      <Header title="Updating live" subtitle="Near realtime channel and recent video statistics" />
      <LiveCounters />
    </Box>
  );
};

export default LiveCountersScene;
