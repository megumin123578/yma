import { Box } from "@mui/material";
import { useParams, Navigate } from "react-router-dom";
import Header from "../../components/Header";
import CredentialsDialog from "../../components/dialogs/CredentialsDialog";

const SECTION_TO_TAB = {
  channels: "add",
  structure: "groups",
  schedule: "schedule",
  logs: "logs",
  users: "manage-user",
};

const SECTION_TO_SUBTITLE = {
  channels: "Manage YouTube channels and credentials.",
  structure: "Organize tokens into groups and projects.",
  schedule: "Configure automated sync schedules.",
  logs: "Inspect background run history.",
  users: "Review and approve user requests.",
};

const ConfigPage = () => {
  const { section = "channels" } = useParams();

  if (!Object.prototype.hasOwnProperty.call(SECTION_TO_TAB, section)) {
    return <Navigate to="/config/channels" replace />;
  }

  const forceTab = SECTION_TO_TAB[section];
  const subtitle = SECTION_TO_SUBTITLE[section];

  return (
    <Box m="20px">
      <Header title="SETTING" subtitle={subtitle} />
      <CredentialsDialog
        open
        inline
        defaultTokenView="card"
        forceTab={forceTab}
      />
    </Box>
  );
};

export default ConfigPage;
