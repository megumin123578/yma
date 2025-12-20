import { Box } from "@mui/material";
import Header from "../../components/Header";
import ChannelCompare from "../../components/ChannelCompare";

const ChannelCompareScene = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="Channel Compare" subtitle="Ranking and anomalies across channels" />
      <ChannelCompare />
    </Box>
  );
};

export default ChannelCompareScene;
