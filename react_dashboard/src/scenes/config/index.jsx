import { useMemo, useState, useEffect } from "react";
import { Box, Tab, Tabs } from "@mui/material";
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
  project: "Manage users, projects, channels, access and roles.",
  schedule: "Configure automated sync schedules.",
  logs: "Inspect background run history.",
};

const ConfigPage = () => {
  const { section = "channels" } = useParams();
  const canManageRoles = useHasPermission("manage_roles");
  const canManageStructure = useHasPermission("manage_structure");

  const projectTabs = useMemo(() => {
    const list = [];
    if (canManageStructure) list.push({ value: "project", label: "Project" });
    if (canManageRoles) list.push({ value: "roles", label: "Roles" });
    return list;
  }, [canManageStructure, canManageRoles]);

  const [projectTab, setProjectTab] = useState(projectTabs[0]?.value || "project");

  useEffect(() => {
    if (!projectTabs.length) return;
    if (!projectTabs.some((t) => t.value === projectTab)) {
      setProjectTab(projectTabs[0].value);
    }
  }, [projectTabs, projectTab]);

  if (section === "users" || section === "structure" || section === "roles") {
    return <Navigate to="/config/project" replace />;
  }

  if (!Object.prototype.hasOwnProperty.call(SECTION_TO_TAB, section)) {
    return <Navigate to="/config/channels" replace />;
  }

  const forceTab = SECTION_TO_TAB[section];
  const subtitle = SECTION_TO_SUBTITLE[section];

  if (section === "project") {
    if (!projectTabs.length) {
      return <NoAccessPage action="manage_structure" />;
    }
    return (
      <Box m="20px" display="flex" flexDirection="column" gap={2}>
        <Header title="SETTING" subtitle={subtitle} />
        {projectTabs.length > 1 && (
          <Tabs
            value={projectTab}
            onChange={(_, next) => setProjectTab(next)}
            sx={{
              minHeight: 36,
              "& .MuiTab-root": {
                minHeight: 36,
                textTransform: "none",
                fontWeight: 700,
              },
            }}
          >
            {projectTabs.map((t) => (
              <Tab key={t.value} value={t.value} label={t.label} />
            ))}
          </Tabs>
        )}
        {projectTab === "project" && canManageStructure && (
          <CredentialsDialog
            open
            inline
            defaultTokenView="card"
            forceTab={forceTab}
          />
        )}
        {projectTab === "roles" && canManageRoles && <RoleManagement />}
      </Box>
    );
  }

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
