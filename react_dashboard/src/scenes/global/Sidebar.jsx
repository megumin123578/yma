import { useState, useContext } from "react";
import { ProSidebar, Menu, MenuItem} from "react-pro-sidebar";
import { Box, IconButton, Typography, useTheme } from "@mui/material";
import { Link, useLocation } from "react-router-dom";
import "react-pro-sidebar/dist/css/styles.css";
import { tokens } from "../../theme";

import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import DatasetIcon from "@mui/icons-material/Dataset";
import DeviceUnknownIcon from "@mui/icons-material/DeviceUnknown";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";

import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import MenuOutlinedIcon from "@mui/icons-material/MenuOutlined";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import InsightsIcon from "@mui/icons-material/Insights";
// import FileUploadIcon from "@mui/icons-material/FileUpload";
import WebhookIcon from '@mui/icons-material/Webhook';
import { UserContext } from "../../context/UserContext";

const Item = ({ title, to, icon, isActive, onClick }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);

  return (
    <MenuItem
      active={isActive}
      style={{ color: colors.grey[100] }}
      icon={icon}
      onClick={onClick}
    >
      <Typography>{title}</Typography>
      <Link to={to} />
    </MenuItem>
  );
};

const Sidebar = ({ isSidebar, setIsSidebar, isMobile = false }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);

  const [isCollapsed, setIsCollapsed] = useState(false);
  const location = useLocation();
  const pathname = location.pathname || "/dashboard";

  const isActivePath = (to) => {
    if (!to) return false;
    if (to === "/dashboard") return pathname === "/" || pathname === "/dashboard";
    return pathname === to || pathname.startsWith(`${to}/`);
  };

  const { user } = useContext(UserContext);
  const closeOnMobile = () => {
    if (isMobile) {
      setIsSidebar?.(false);
    }
  };

  const getSidebarAvatar = () => {
    if (!user?.avatar) {
      return "../../assets/user.jpg";
    }

    if (user.avatar.startsWith("blob:")) {
      return "../../assets/user.jpg";
    }

    return `${process.env.REACT_APP_API_URL || ""}${user.avatar}`;
  };

  return (
    <>
      {isMobile && isSidebar && (
        <Box
          onClick={() => setIsSidebar?.(false)}
          sx={{
            position: "fixed",
            inset: 0,
            bgcolor: "rgba(2,6,23,0.45)",
            backdropFilter: "blur(2px)",
            zIndex: 1198,
          }}
        />
      )}
      <Box
      sx={{
        height: "100vh",
        position: isMobile ? "fixed" : "relative",
        top: 0,
        left: 0,
        zIndex: isMobile ? 1199 : "auto",
        transform: isMobile ? (isSidebar ? "translateX(0)" : "translateX(-110%)") : "none",
        transition: isMobile ? "transform 220ms ease" : "none",
        "& .pro-sidebar": {
          height: "100vh",
          width: isMobile ? "min(82vw, 320px)" : undefined,
        },
        "& .pro-sidebar-inner": {
          background: `${colors.primary[400]} !important`,
          cursor: "pointer",
        },
        "& .pro-sidebar, & .pro-sidebar-inner, & .pro-sidebar-layout": {
          transition: "none !important",
        },
        "& .pro-icon-wrapper": {
          backgroundColor: "transparent !important",
        },
        "& .pro-inner-item": {
          padding: "5px 35px 5px 20px !important",
        },
        "& .pro-inner-item:hover": {
          color: "#868dfb !important",
        },
        "& .pro-menu-item.active": {
          color: "#6870fa !important",
        },
      }}
    >
      <ProSidebar collapsed={isCollapsed}>
        <Menu iconShape="square">
          {/* LOGO */}
          <MenuItem
            onClick={() => setIsCollapsed(!isCollapsed)}
            icon={isCollapsed ? <MenuOutlinedIcon /> : undefined}
            style={{
              margin: "10px 0 20px 0",
              color: colors.grey[100],
            }}
          >
            {!isCollapsed && (
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems="center"
                ml="15px"
              >
                <Typography
                  variant="h3"
                  color={colors.grey[100]}
                  sx={{
                    fontSize: "1.1rem",
                    lineHeight: 1.2,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    pr: "8px",
                    flexGrow: 1,
                    minWidth: 0,
                  }}
                >
                  YT Manage App
                </Typography>
                <IconButton onClick={() => setIsCollapsed(!isCollapsed)}>
                  <MenuOutlinedIcon />
                </IconButton>
              </Box>
            )}
          </MenuItem>

          {/* USER INFO */}
          {!isCollapsed && (
            <Box mb="25px">
              <Box display="flex" justifyContent="center" alignItems="center">
                <img
                  alt="profile-user"
                  width="100px"
                  height="100px"
                  src={getSidebarAvatar()}
                  style={{
                    cursor: "pointer",
                    borderRadius: "50%",
                    objectFit: "cover",
                  }}
                />
              </Box>

              <Box textAlign="center">
                <Typography
                  variant="h2"
                  color={colors.grey[100]}
                  fontWeight="bold"
                  sx={{ m: "10px 0 0 0" }}
                >
                  {user?.name || "Admin"}
                </Typography>

              </Box>
            </Box>
          )}

          {/* MENU */}
          <Box paddingLeft={isCollapsed ? undefined : "10%"}>
            <Item
              title="Dashboard"
              to="/dashboard"
              icon={<HomeOutlinedIcon />}
              isActive={isActivePath("/dashboard")}
              onClick={closeOnMobile}
            />

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Analytics
            </Typography>

            <Item
              title="Content"
              to="/content"
              icon={<DatasetIcon />}
              isActive={isActivePath("/content")}
              onClick={closeOnMobile}
            />

            <Item
              title="Traffic Source"
              to="/traffic_source"
              icon={<DeviceUnknownIcon />}
              isActive={isActivePath("/traffic_source")}
              onClick={closeOnMobile}
            />

            <Item
              title="Geography Chart"
              to="/geography"
              icon={<MapOutlinedIcon />}
              isActive={isActivePath("/geography")}
              onClick={closeOnMobile}
            />

            <Item
              title="Audience Analytics"
              to="/audience_analytics"
              icon={<GroupsOutlinedIcon />}
              isActive={isActivePath("/audience_analytics")}
              onClick={closeOnMobile}
            />

            <Item
              title="Reach"
              to="/reach"
              icon={<VisibilityOutlinedIcon />}
              isActive={isActivePath("/reach")}
              onClick={closeOnMobile}
            />

            <Item
              title="Revenue"
              to="/revenue"
              icon={<AttachMoneyIcon />}
              isActive={isActivePath("/revenue")}
              onClick={closeOnMobile}
            />

            <Item
              title="Live Counters"
              to="/live_counters"
              icon={<InsightsIcon />}
              isActive={isActivePath("/live_counters")}
              onClick={closeOnMobile}
            />
            

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Statistics
            </Typography>

            <Item
              title="Channel Compare"
              to="/channel_compare"
              icon={<BarChartOutlinedIcon />}
              isActive={isActivePath("/channel_compare")}
              onClick={closeOnMobile}
            />

            <Item
              title="Rivals Channel"
              to="/rivals"
              icon={<WebhookIcon />}
              isActive={isActivePath("/rivals")}
              onClick={closeOnMobile}
            />

            <Typography
              variant="h6"
              color={colors.grey[300]}
              sx={{ m: "15px 0 5px 20px" }}
            >
              Automation
            </Typography>

            <Item
              title="SMMStore Orders"
              to="/smmstore"
              icon={<AttachMoneyIcon />}
              isActive={isActivePath("/smmstore")}
              onClick={closeOnMobile}
            />

            <Item
              title="SMMStore Analytics"
              to="/smmstore_analytics"
              icon={<BarChartOutlinedIcon />}
              isActive={isActivePath("/smmstore_analytics")}
              onClick={closeOnMobile}
            />

            {/* <Item
              title="Tool Upload Short"
              to="/tool_upload_short"
              icon={<FileUploadIcon />}
              selected={selected}
              setSelected={setSelected}
            /> */}
          </Box>
        </Menu>
      </ProSidebar>
      </Box>
    </>
  );
};

export default Sidebar;
