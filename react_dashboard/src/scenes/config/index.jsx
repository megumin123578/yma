import { Box } from "@mui/material";
import { useParams, Navigate } from "react-router-dom";
import Header from "../../components/Header";
import CredentialsDialog from "../../components/dialogs/CredentialsDialog";
import RoleManagement from "../../components/RoleManagement";
import NoAccessPage from "../../components/NoAccessPage";
import { useHasPermission } from "../../context/UserContext";

const SECTION_TO_TAB = {
  channels: "add",
  project: "groups",
  schedule: "schedule",
  logs: "logs",
};

const SECTION_TO_SUBTITLE = {
  channels: "Manage YouTube channels and credentials.",
  project: "Manage users, projects, channels and access.",
  schedule: "Configure automated sync schedules.",
  logs: "Inspect background run history.",
  roles: "Define roles and assign permissions.",
};

const ConfigPage = () => {
  const { section = "channels" } = useParams();
  const canManageRoles = useHasPermission("manage_roles");

  if (section === "users" || section === "structure") {
    return <Navigate to="/config/project" replace />;
  }

  if (section === "roles") {
    if (!canManageRoles) {
      return <NoAccessPage action="manage_roles" />;
    }
    return (
      <Box m="20px">
        <Header title="SETTING" subtitle={SECTION_TO_SUBTITLE.roles} />
        <RoleManagement />
      </Box>
    );
  }

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
