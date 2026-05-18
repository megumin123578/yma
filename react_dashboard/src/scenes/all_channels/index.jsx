import { useEffect, useMemo, useState } from "react";
import { Box, FormControl, InputLabel, MenuItem, Select } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import Header from "../../components/Header";
import ContentAnalytics from "../../components/content/ContentContainer";
import api from "../../services/api";
import { listTokens } from "../../services/userService";
import {
  getSharedFilterControlSx,
  getSharedSelectMenuProps,
} from "../../components/filterStyles";

const CONTENT_ALL_CHANNELS_VALUE = "__all__";
const ALL_PROJECTS_VALUE = "__all_projects__";
const STORAGE_KEY = "all_channels_project_filter";

const AllChannelsScene = () => {
  const theme = useTheme();
  const filterControlSx = getSharedFilterControlSx(theme);
  const selectMenuProps = getSharedSelectMenuProps(theme);
  const [channels, setChannels] = useState([]);
  const [allProjects, setAllProjects] = useState([]);
  const [project, setProject] = useState(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) || ALL_PROJECTS_VALUE;
    } catch {
      return ALL_PROJECTS_VALUE;
    }
  });

  useEffect(() => {
    let active = true;
    api
      .get("/api/content/channels")
      .then((res) => {
        if (!active) return;
        const items = Array.isArray(res.data?.items) ? res.data.items : [];
        setChannels(items);
      })
      .catch(() => {
        if (!active) return;
        setChannels([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    listTokens()
      .then((data) => {
        if (!active) return;
        const items = Array.isArray(data?.projects) ? data.projects : [];
        const names = items
          .map((item) => String(item?.project_name || "").trim())
          .filter(Boolean);
        setAllProjects(names);
      })
      .catch(() => {
        if (!active) return;
        setAllProjects([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const projectOptions = useMemo(() => {
    const names = new Set(allProjects);
    channels.forEach((c) => {
      const name = String(c?.project_name || "").trim();
      if (name) names.add(name);
    });
    return Array.from(names).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base", numeric: true })
    );
  }, [allProjects, channels]);

  const allowedChannelIds = useMemo(() => {
    if (project === ALL_PROJECTS_VALUE) return null;
    const out = new Set();
    channels.forEach((c) => {
      if (String(c?.project_name || "").trim() === project) {
        const v = String(c?.value || "").trim();
        if (v) out.add(v);
      }
    });
    return out;
  }, [channels, project]);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, project);
    } catch {
      // ignore storage errors
    }
  }, [project]);

  useEffect(() => {
    if (project === ALL_PROJECTS_VALUE) return;
    if (!projectOptions.includes(project)) {
      setProject(ALL_PROJECTS_VALUE);
    }
  }, [project, projectOptions]);

  const projectFilter = (
    <FormControl
      size="small"
      sx={{
        ...filterControlSx,
        flex: { xs: "1 1 100%", sm: "1 1 220px" },
      }}
    >
      <InputLabel>Project</InputLabel>
      <Select
        value={project}
        label="Project"
        onChange={(e) => setProject(e.target.value)}
        MenuProps={selectMenuProps}
      >
        <MenuItem value={ALL_PROJECTS_VALUE}>All projects</MenuItem>
        {projectOptions.map((name) => (
          <MenuItem key={name} value={name}>
            {name}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );

  return (
    <Box mx="20px" mt="0" mb="20px">
      <Header title="OVERVIEW" subtitle="Cross-channel content overview" />
      <Box mt={3}>
        <ContentAnalytics
          hideChannelSwitcher
          forcedChannelId={CONTENT_ALL_CHANNELS_VALUE}
          allowedChannelIds={allowedChannelIds}
          leadingFilters={projectFilter}
        />
      </Box>
    </Box>
  );
};

export default AllChannelsScene;
