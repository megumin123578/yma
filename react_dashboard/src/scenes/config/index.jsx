import { Box } from "@mui/material";
import Header from "../../components/Header";
import CredentialsDialog from "../../components/dialogs/CredentialsDialog";

const ConfigPage = () => {
  return (
    <Box m="20px">
      <Header
        title="CONFIG"
        subtitle="Manage Google accounts, schedules, and sync logs."
      />
      <CredentialsDialog open inline defaultTokenView="card" />
    </Box>
  );
};

export default ConfigPage;
