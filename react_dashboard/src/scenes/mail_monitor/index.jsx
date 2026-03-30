import { Box } from "@mui/material";
import Header from "../../components/Header";
import MailMonitor from "../../components/MailMonitor";


const MailMonitorScene = () => {
  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="EMAIL MANAGER" subtitle="Welcome to your email manager" />
      <Box mt={3}>
        <MailMonitor />
      </Box>
    </Box>
  );
};


export default MailMonitorScene;
