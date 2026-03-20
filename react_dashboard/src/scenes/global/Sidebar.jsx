import { useContext } from "react";
import { ProSidebar, Menu, MenuItem} from "react-pro-sidebar";
import { Box, Typography, useTheme } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { Link, useLocation } from "react-router-dom";
import "react-pro-sidebar/dist/css/styles.css";
import { tokens } from "../../theme";

import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import DatasetIcon from "@mui/icons-material/Dataset";
import DeviceUnknownIcon from "@mui/icons-material/DeviceUnknown";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";

import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
// import FileUploadIcon from "@mui/icons-material/FileUpload";
import WebhookIcon from '@mui/icons-material/Webhook';
import SettingsIcon from "@mui/icons-material/Settings";
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
      <Typography sx={{ fontSize: "0.95rem", fontWeight: isActive ? 700 : 600 }}>
        {title}
      </Typography>
      <Link to={to} />
    </MenuItem>
  );
};

const SectionLabel = ({ children, isCollapsed }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);

  if (isCollapsed) {
    return <Box sx={{ height: 14 }} />;
  }

  return (
    <Typography
      variant="h6"
      color={theme.palette.mode === "dark" ? colors.grey[300] : colors.grey[500]}
      sx={{
        m: "20px 0 8px 18px",
        fontSize: "0.69rem",
        fontWeight: 800,
        letterSpacing: "0.16em",
        textTransform: "uppercase",
      }}
    >
      {children}
    </Typography>
  );
};

const Sidebar = ({ isSidebar, setIsSidebar, isMobile = false }) => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const location = useLocation();
  const pathname = location.pathname || "/dashboard";
  const desktopSidebarWidth = 280;
  const sidebarWidth = isMobile
    ? "min(82vw, 320px)"
    : `${isSidebar ? desktopSidebarWidth : 0}px`;

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
            bgcolor: "rgba(2,6,23,0.52)",
            backdropFilter: "blur(4px)",
            zIndex: 1198,
          }}
        />
      )}
      <Box
        sx={{
        height: "100vh",
        position: isMobile ? "fixed" : "relative",
        top: isMobile ? 0 : "auto",
        left: isMobile ? 0 : "auto",
        zIndex: isMobile ? 1199 : "auto",
        width: isMobile ? "auto" : sidebarWidth,
        minWidth: isMobile ? "auto" : sidebarWidth,
        flexShrink: 0,
        overflow: "hidden",
        opacity: isMobile ? (isSidebar ? 1 : 0) : 1,
        pointerEvents: isMobile
          ? (isSidebar ? "auto" : "none")
          : (isSidebar ? "auto" : "none"),
        transform: isMobile
          ? (isSidebar ? "translateX(0)" : "translateX(-110%)")
          : "none",
        transition: isMobile
          ? "opacity 180ms ease, transform 240ms cubic-bezier(0.22, 1, 0.36, 1)"
          : "width 240ms cubic-bezier(0.22, 1, 0.36, 1)",
        "& .pro-sidebar": {
          height: "100vh",
          width: sidebarWidth,
          minWidth: sidebarWidth,
          boxShadow: isMobile
            ? "0 20px 50px rgba(2,6,23,0.45)"
            : isSidebar
              ? "0 18px 48px rgba(2,6,23,0.18)"
              : "none",
          transition: "width 200ms cubic-bezier(0.22, 1, 0.36, 1) !important",
        },
        "& .pro-sidebar-inner": {
          background: `${
            theme.palette.mode === "dark"
              ? "linear-gradient(180deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.98) 62%, rgba(20,83,45,0.22) 100%)"
              : "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 68%, rgba(219,234,254,0.88) 100%)"
          } !important`,
          borderRight: `1px solid ${
            theme.palette.mode === "dark"
              ? "rgba(255,255,255,0.08)"
              : "rgba(15,23,42,0.08)"
          }`,
          overflowY: "auto",
          overflowX: "hidden",
          scrollbarWidth: "thin",
          scrollbarColor:
            theme.palette.mode === "dark"
              ? "rgba(148,163,184,0.4) transparent"
              : "rgba(100,116,139,0.35) transparent",
          "&::-webkit-scrollbar": {
            width: 8,
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor:
              theme.palette.mode === "dark"
                ? "rgba(148,163,184,0.28)"
                : "rgba(100,116,139,0.24)",
            borderRadius: 999,
          },
        },
        "& .pro-icon-wrapper": {
          backgroundColor: "transparent !important",
          width: 36,
          minWidth: 36,
          height: 36,
          minHeight: 36,
          borderRadius: 12,
          display: "grid",
          placeItems: "center",
          transition: "all 180ms ease",
        },
        "& .pro-inner-item": {
          position: "relative",
          margin: "4px 12px !important",
          padding: "10px 16px !important",
          borderRadius: "14px !important",
          transition: "all 180ms ease !important",
        },
        "& .pro-inner-item:focus-visible": {
          outline: `2px solid ${theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb"}`,
          outlineOffset: 2,
        },
        "& .pro-inner-item:hover": {
          color: `${theme.palette.mode === "dark" ? "#f8fafc" : "#0f172a"} !important`,
          background: `${
            theme.palette.mode === "dark"
              ? "rgba(255,255,255,0.06)"
              : "rgba(15,23,42,0.05)"
          } !important`,
          transform: "translateX(3px)",
        },
        "& .pro-inner-item:hover .pro-icon-wrapper": {
          backgroundColor: `${
            theme.palette.mode === "dark"
              ? "rgba(125,224,210,0.12)"
              : "rgba(37,99,235,0.1)"
          } !important`,
        },
        "& .pro-menu-item.active": {
          color: `${theme.palette.mode === "dark" ? "#ffffff" : "#0f172a"} !important`,
        },
        "& .pro-menu-item.active > .pro-inner-item": {
          background: `${
            theme.palette.mode === "dark"
              ? "linear-gradient(90deg, rgba(125,224,210,0.18) 0%, rgba(59,130,246,0.14) 100%)"
              : "linear-gradient(90deg, rgba(37,99,235,0.12) 0%, rgba(14,165,233,0.08) 100%)"
          } !important`,
          boxShadow: `${
            theme.palette.mode === "dark"
              ? "0 10px 24px rgba(15,23,42,0.28)"
              : "0 10px 20px rgba(37,99,235,0.12)"
          }`,
        },
        "& .pro-menu-item.active > .pro-inner-item:before": {
          content: '""',
          position: "absolute",
          left: 0,
          top: 10,
          bottom: 10,
          width: 4,
          borderRadius: 999,
          background: theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb",
        },
        "& .pro-menu-item.active .pro-icon-wrapper": {
          backgroundColor: `${
            theme.palette.mode === "dark"
              ? "rgba(125,224,210,0.16)"
              : "rgba(37,99,235,0.12)"
          } !important`,
          color: `${theme.palette.mode === "dark" ? "#dffcf6" : "#1d4ed8"} !important`,
        },
        "& .pro-menu-item > .pro-inner-item > .pro-item-content": {
          transition: "opacity 150ms ease, transform 180ms ease",
        },
      }}
    >
      <ProSidebar collapsed={false}>
        <Menu iconShape="square">
          {/* USER INFO */}
          <Box
            px="16px"
            mb="22px"
            sx={{
              transition: "padding 200ms ease",
            }}
          >
            <Box
              sx={{
                p: 1.5,
                borderRadius: 4,
                background: theme.palette.mode === "dark"
                  ? "rgba(255,255,255,0.04)"
                  : "rgba(15,23,42,0.04)",
                border: `1px solid ${
                  theme.palette.mode === "dark"
                    ? "rgba(255,255,255,0.08)"
                    : "rgba(15,23,42,0.08)"
                }`,
              }}
            >
              <Box display="flex" justifyContent="center" alignItems="center">
                <img
                  alt="profile-user"
                  width="72px"
                  height="72px"
                  src={getSidebarAvatar()}
                  style={{
                    cursor: "pointer",
                    borderRadius: "50%",
                    objectFit: "cover",
                    border: `2px solid ${alpha(theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb", 0.35)}`,
                    boxShadow: `0 10px 24px ${alpha(theme.palette.mode === "dark" ? "#000000" : "#1e3a8a", 0.18)}`,
                  }}
                />
              </Box>

              <Box textAlign="center" mt={1.25}>
                <Typography
                  variant="h6"
                  color={theme.palette.mode === "dark" ? colors.grey[100] : colors.primary[100]}
                  fontWeight="bold"
                  sx={{ lineHeight: 1.2 }}
                >
                  {user?.name || "Admin"}
                </Typography>
              </Box>
            </Box>
          </Box>

          {/* MENU */}
          <Box paddingLeft="6px" paddingRight="6px">
            <Item
              title="Dashboard"
              to="/dashboard"
              icon={<HomeOutlinedIcon />}
              isActive={isActivePath("/dashboard")}
              onClick={closeOnMobile}
            />

            <SectionLabel isCollapsed={false}>Analytics</SectionLabel>

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

            <SectionLabel isCollapsed={false}>Statistics</SectionLabel>

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

            <SectionLabel isCollapsed={false}>Automation</SectionLabel>

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

            <SectionLabel isCollapsed={false}>Setting</SectionLabel>

            <Item
              title="Config"
              to="/config"
              icon={<SettingsIcon />}
              isActive={isActivePath("/config")}
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
