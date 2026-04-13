import { ProSidebar, Menu, MenuItem, SubMenu } from "react-pro-sidebar";
import { Box, Typography, useTheme } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useContext, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import "react-pro-sidebar/dist/css/styles.css";
import { tokens } from "../../theme";

import HomeOutlinedIcon from "@mui/icons-material/HomeOutlined";
import DatasetIcon from "@mui/icons-material/Dataset";
import ViewModuleOutlinedIcon from "@mui/icons-material/ViewModuleOutlined";
import DeviceUnknownIcon from "@mui/icons-material/DeviceUnknown";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import BarChartOutlinedIcon from "@mui/icons-material/BarChartOutlined";
import AttachMoneyIcon from "@mui/icons-material/AttachMoney";
import MapOutlinedIcon from "@mui/icons-material/MapOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import MailOutlineRoundedIcon from "@mui/icons-material/MailOutlineRounded";
import WebhookIcon from "@mui/icons-material/Webhook";
import QueryStatsIcon from "@mui/icons-material/QueryStats";
import AutoModeIcon from "@mui/icons-material/AutoMode";
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
      <Typography sx={{ fontSize: "0.88rem", fontWeight: isActive ? 700 : 600 }}>
        {title}
      </Typography>
      <Link to={to} />
    </MenuItem>
  );
};

const Sidebar = ({ isSidebar, setIsSidebar, isMobile = false }) => {
  const theme = useTheme();
  const location = useLocation();
  const { user } = useContext(UserContext);
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

  const inGroup = (routes) => routes.some((r) => isActivePath(r));

  const [openAnalytics, setOpenAnalytics] = useState(() =>
    inGroup(["/all_channels", "/content", "/traffic_source", "/geography", "/audience_analytics", "/reach", "/revenue"])
  );
  const [openStatistics, setOpenStatistics] = useState(() =>
    inGroup(["/channel_compare", "/rivals"])
  );
  const [openAutomation, setOpenAutomation] = useState(() =>
    inGroup(["/smmstore", "/smmstore_analytics", "/mail_monitor"])
  );

  const closeOnMobile = () => {
    if (isMobile) setIsSidebar?.(false);
  };

  const sidebarAvatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? `${process.env.REACT_APP_API_URL || ""}${user.avatar}`
      : "../../assets/user.jpg";

  const subMenuTitleSx = {
    fontSize: "0.82rem",
    fontWeight: 700,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
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
            ? isSidebar ? "auto" : "none"
            : isSidebar ? "auto" : "none",
          transform: isMobile
            ? isSidebar ? "translateX(0)" : "translateX(-110%)"
            : "none",
          transition: isMobile
            ? "opacity 180ms ease, transform 240ms cubic-bezier(0.22, 1, 0.36, 1)"
            : "none",
          "& .pro-sidebar": {
            height: "100vh",
            width: sidebarWidth,
            minWidth: sidebarWidth,
            overflow: "hidden !important",
            boxShadow: isMobile
              ? "0 20px 50px rgba(2,6,23,0.45)"
              : isSidebar
                ? "0 18px 48px rgba(2,6,23,0.18)"
                : "none",
            transition: isMobile
              ? "width 200ms cubic-bezier(0.22, 1, 0.36, 1) !important"
              : "none !important",
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
            overflowY: "auto !important",
            overflowX: "hidden !important",
          },
          "& .pro-sidebar .pro-menu": {
            overflow: "visible !important",
          },
          "& .pro-sidebar .pro-menu > ul": {
            overflow: "visible !important",
          },
          "& .pro-icon-wrapper": {
            backgroundColor: "transparent !important",
            width: 32,
            minWidth: 32,
            height: 32,
            minHeight: 32,
            borderRadius: 10,
            display: "grid",
            placeItems: "center",
            transition: "all 180ms ease",
          },
          "& .pro-inner-item": {
            position: "relative",
            margin: "2px 10px !important",
            padding: "7px 12px !important",
            minHeight: "unset !important",
            borderRadius: "12px !important",
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
            backgroundColor: "transparent !important",
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
            top: 7,
            bottom: 7,
            width: 3,
            borderRadius: 999,
            background: theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb",
          },
          "& .pro-menu-item.active .pro-icon-wrapper": {
            backgroundColor: "transparent !important",
            color: `${theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb"} !important`,
          },
          "& .pro-menu-item > .pro-inner-item > .pro-item-content": {
            transition: "opacity 150ms ease, transform 180ms ease",
          },
          // SubMenu styles
          "& .pro-sub-menu > .pro-inner-item": {
            color: `${theme.palette.mode === "dark" ? "#94a3b8" : "#64748b"} !important`,
          },
          "& .pro-sub-menu.open > .pro-inner-item": {
            color: `${theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb"} !important`,
          },
          "& .pro-inner-list-item": {
            backgroundColor: "transparent !important",
            paddingLeft: "0 !important",
          },
          "& .pro-inner-list-item > div > ul": {
            paddingTop: "2px !important",
            paddingBottom: "2px !important",
          },
          "& .pro-arrow-wrapper": {
            paddingRight: "4px !important",
          },
          "& .pro-arrow": {
            borderColor: `${theme.palette.mode === "dark" ? "#94a3b8" : "#64748b"} !important`,
            borderWidth: "1.5px !important",
          },
          "& .pro-sub-menu.open > .pro-inner-item .pro-arrow": {
            borderColor: `${theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb"} !important`,
          },
        }}
      >
        <ProSidebar collapsed={false}>
          <Menu iconShape="square">
            <Box px="14px" pt="8px" pb="4px">
              <Box sx={{ px: 0.75, py: 0.75 }}>
                <Box display="flex" justifyContent="center">
                  <Box
                    component="img"
                    alt="profile-user"
                    src={sidebarAvatarSrc}
                    sx={{
                      width: 60,
                      height: 60,
                      borderRadius: "50%",
                      objectFit: "cover",
                      flexShrink: 0,
                      border: `2px solid ${alpha(
                        theme.palette.mode === "dark" ? "#7de0d2" : "#2563eb",
                        0.28
                      )}`,
                      boxShadow: `0 10px 24px ${alpha(
                        theme.palette.mode === "dark" ? "#000000" : "#1e3a8a",
                        0.16
                      )}`,
                    }}
                  />
                </Box>
                <Typography
                  color={theme.palette.mode === "dark" ? "#f8fafc" : "#0f172a"}
                  sx={{
                    mt: 0.75,
                    fontSize: "0.88rem",
                    fontWeight: 700,
                    lineHeight: 1.2,
                    textAlign: "center",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {user?.name || "Admin"}
                </Typography>
              </Box>
            </Box>

            {/* MENU */}
            <Box paddingLeft="6px" paddingRight="6px" pt="2px" pb="8px">
              <Item
                title="Dashboard"
                to="/dashboard"
                icon={<HomeOutlinedIcon />}
                isActive={isActivePath("/dashboard")}
                onClick={closeOnMobile}
              />

              <SubMenu
                title={<Typography sx={subMenuTitleSx}>Analytics</Typography>}
                icon={<BarChartOutlinedIcon />}
                open={openAnalytics}
                onOpenChange={setOpenAnalytics}
              >
                <Item
                  title="All Channels"
                  to="/all_channels"
                  icon={<ViewModuleOutlinedIcon />}
                  isActive={isActivePath("/all_channels")}
                  onClick={closeOnMobile}
                />
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
              </SubMenu>

              <SubMenu
                title={<Typography sx={subMenuTitleSx}>Statistics</Typography>}
                icon={<QueryStatsIcon />}
                open={openStatistics}
                onOpenChange={setOpenStatistics}
              >
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
              </SubMenu>

              <SubMenu
                title={<Typography sx={subMenuTitleSx}>Automation</Typography>}
                icon={<AutoModeIcon />}
                open={openAutomation}
                onOpenChange={setOpenAutomation}
              >
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
                <Item
                  title="Email Manager"
                  to="/mail_monitor"
                  icon={<MailOutlineRoundedIcon />}
                  isActive={isActivePath("/mail_monitor")}
                  onClick={closeOnMobile}
                />
              </SubMenu>

            </Box>
          </Menu>
        </ProSidebar>
      </Box>
    </>
  );
};

export default Sidebar;
