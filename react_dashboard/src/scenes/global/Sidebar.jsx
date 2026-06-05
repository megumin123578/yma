import { Box, Typography, useTheme } from "@mui/material";
import { alpha } from "@mui/material/styles";
import { useContext } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Menu,
  MenuItem,
  Sidebar as ProSidebar,
  menuClasses,
  sidebarClasses,
  SubMenu,
} from "react-pro-sidebar";

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
import TravelExploreOutlinedIcon from "@mui/icons-material/TravelExploreOutlined";
import ManageSearchOutlinedIcon from "@mui/icons-material/ManageSearchOutlined";
import AutoModeIcon from "@mui/icons-material/AutoMode";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import SmartDisplayOutlinedIcon from "@mui/icons-material/SmartDisplayOutlined";

import { UserContext } from "../../context/UserContext";
import { tokens } from "../../theme";
import { resolveApiAssetUrl } from "../../config";
import { prefetchContentPage } from "../../utils/contentPrefetch";

const Item = ({ title, to, icon, isActive, onClick, onMouseEnter, isCompact = false }) => (
  <MenuItem
    active={isActive}
    icon={icon}
    component={<Link to={to} />}
    onClick={onClick}
    onMouseEnter={onMouseEnter}
    title={isCompact ? title : undefined}
    aria-label={title}
  >
    {title}
  </MenuItem>
);

const Sidebar = ({
  desktopSidebarMode = "expanded",
  isMobileSidebarOpen = false,
  setIsMobileSidebarOpen,
  isMobile = false,
}) => {
  const theme = useTheme();
  const location = useLocation();
  const { user } = useContext(UserContext);
  const colorTokens = tokens(theme.palette.mode);

  const pathname = location.pathname || "/dashboard";
  const desktopSidebarWidth = 280;
  const desktopCompactSidebarWidth = 68;
  const mobileSidebarWidth = "min(82vw, 320px)";

  const isDesktopCompact = !isMobile && desktopSidebarMode === "compact";
  const isDesktopHidden = !isMobile && desktopSidebarMode === "hidden";
  const shellWidth = isMobile
    ? mobileSidebarWidth
    : isDesktopHidden
      ? "0px"
      : isDesktopCompact
        ? `${desktopCompactSidebarWidth}px`
        : `${desktopSidebarWidth}px`;

  const accentColor =
    theme.palette.mode === "dark" ? colorTokens.greenAccent[400] : colorTokens.blueAccent[500];
  const textColor = theme.palette.text.primary;
  const mutedColor = theme.palette.text.secondary;
  const hoverBg =
    theme.palette.mode === "dark"
      ? "rgba(255,255,255,0.06)"
      : "rgba(15,23,42,0.05)";
  const activeBg =
    theme.palette.mode === "dark"
      ? "linear-gradient(90deg, rgba(125,224,210,0.18) 0%, rgba(59,130,246,0.14) 100%)"
      : "linear-gradient(90deg, rgba(37,99,235,0.12) 0%, rgba(14,165,233,0.08) 100%)";
  const sidebarBackground =
    theme.palette.mode === "dark"
      ? "linear-gradient(180deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.98) 62%, rgba(20,83,45,0.22) 100%)"
      : "linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 68%, rgba(219,234,254,0.88) 100%)";
  const popperBackground =
    theme.palette.mode === "dark"
      ? "linear-gradient(180deg, rgba(17,24,39,0.98) 0%, rgba(15,23,42,0.98) 100%)"
      : "linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(248,250,252,0.98) 100%)";

  const isActivePath = (to) => {
    if (!to) return false;
    if (to === "/dashboard") return pathname === "/" || pathname === "/dashboard";
    return pathname === to || pathname.startsWith(`${to}/`);
  };

  const inGroup = (routes) => routes.some((route) => isActivePath(route));
  const defaultOpenAnalytics = inGroup([
    "/all_channels",
    "/content",
    "/traffic_source",
    "/geography",
    "/audience_analytics",
    "/reach",
    "/revenue",
  ]);
  const defaultOpenStatistics = inGroup(["/channel_compare", "/rivals"]);
  const defaultOpenResearch = inGroup(["/research", "/research/config", "/research/seo", "/research/summary"]);
  const defaultOpenAutomation = inGroup([
    "/smmstore",
    "/smmstore_analytics",
    "/mail_monitor",
  ]);
  const defaultOpenSettings = inGroup([
    "/config",
    "/config/channels",
    "/config/project",
    "/config/schedule",
    "/config/logs",
  ]);
  const isAdmin = !!user?.is_admin;
  const canDashboard = true;
  const canContent = true;
  const canAllChannels = true;
  const canChannelCompare = true;
  const canAudience = true;
  const canRevenue = true;
  const canReach = true;
  const canTraffic = true;
  const canGeography = true;
  const canSmmstore = true;
  const canMail = true;
  const canRivals = true;
  const canResearch = true;
  const canConfig = true;
  const canManageStructure = true;
  const canManageRoles = true;

  const closeOnMobile = () => {
    if (isMobile) setIsMobileSidebarOpen?.(false);
  };

  const sidebarAvatarSrc =
    user?.avatar && !user.avatar.startsWith("blob:")
      ? resolveApiAssetUrl(user.avatar)
      : "/assets/user.jpg";

  const subMenuTitleSx = {
    fontSize: "0.82rem",
    fontWeight: 700,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
  };

  const menuItemStyles = {
    root: ({ level }) => ({
      margin:
        level === 0
          ? isDesktopCompact
            ? "4px 8px"
            : "2px 10px"
          : "2px 8px 2px 14px",
    }),
    button: ({ level, active, open, disabled }) => ({
      position: "relative",
      minHeight: "unset",
      width: "100%",
      maxWidth: "100%",
      boxSizing: "border-box",
      borderRadius: 12,
      padding:
        level === 0
          ? isDesktopCompact
            ? "9px 0"
            : "7px 12px"
          : "7px 12px",
      justifyContent: level === 0 && isDesktopCompact ? "center" : "flex-start",
      color: active || open ? textColor : mutedColor,
      transition: "all 180ms ease",
      ...(disabled
        ? {}
        : {
            "&:hover": {
              backgroundColor: hoverBg,
              color: textColor,
              transform:
                level === 0
                  ? isDesktopCompact
                    ? "translateY(-1px)"
                    : "translateX(3px)"
                  : "none",
            },
          }),
      "&:focus-visible": {
        outline: `2px solid ${accentColor}`,
        outlineOffset: 2,
      },
      ...(active && {
        background: `${activeBg} !important`,
        boxShadow:
          theme.palette.mode === "dark"
            ? "0 10px 24px rgba(15,23,42,0.28)"
            : "0 10px 20px rgba(37,99,235,0.12)",
        "&::before": {
          content: '""',
          position: "absolute",
          left: level === 0 && isDesktopCompact ? 6 : 0,
          top: level === 0 && isDesktopCompact ? 9 : 7,
          bottom: level === 0 && isDesktopCompact ? 9 : 7,
          width: 3,
          borderRadius: 999,
          background: accentColor,
        },
      }),
    }),
    label: ({ level, active }) => ({
      ...(level === 0 && isDesktopCompact
        ? {
            display: "none",
          }
        : {}),
      fontSize: level === 0 ? "0.88rem" : "0.84rem",
      fontWeight: active ? 700 : level === 0 ? 600 : 500,
    }),
    icon: ({ active }) => ({
      width: 32,
      minWidth: 32,
      height: 32,
      minHeight: 32,
      borderRadius: 10,
      display: "grid",
      placeItems: "center",
      color: active ? accentColor : undefined,
    }),
    subMenuContent: ({ level }) => ({
      width: "100%",
      maxWidth: "100%",
      minWidth: 0,
      boxSizing: "border-box",
      overflowX: "hidden !important",
      backgroundColor: "transparent",
      ...(isDesktopCompact
        ? {
            background: popperBackground,
            border: `1px solid ${alpha(
              theme.palette.mode === "dark" ? theme.palette.common.white : textColor,
              0.08
            )}`,
            borderRadius: 16,
            boxShadow:
              theme.palette.mode === "dark"
                ? "0 18px 36px rgba(2,6,23,0.46)"
                : "0 18px 36px rgba(15,23,42,0.12)",
            padding: "10px 8px",
            overflow: "hidden",
          }
        : {
            paddingTop: level === 0 ? 2 : 0,
            paddingBottom: level === 0 ? 2 : 0,
          }),
    }),
    SubMenuExpandIcon: ({ open }) => ({
      ...(isDesktopCompact
        ? {
            display: "none",
          }
        : {}),
      color: open ? accentColor : mutedColor,
      marginRight: isDesktopCompact ? 0 : 4,
    }),
  };

  return (
    <>
      {isMobile && isMobileSidebarOpen ? (
        <Box
          onClick={() => setIsMobileSidebarOpen?.(false)}
          sx={{
            position: "fixed",
            inset: 0,
            bgcolor: "rgba(2,6,23,0.52)",
            backdropFilter: "blur(4px)",
            zIndex: 1198,
          }}
        />
      ) : null}

      <Box
        sx={{
          height: "100vh",
          position: isMobile ? "fixed" : "relative",
          top: isMobile ? 0 : "auto",
          left: isMobile ? 0 : "auto",
          zIndex: isMobile ? 1199 : "auto",
          width: isMobile ? "auto" : shellWidth,
          minWidth: isMobile ? "auto" : shellWidth,
          flexShrink: 0,
          overflow: "hidden",
          opacity: isMobile ? (isMobileSidebarOpen ? 1 : 0) : isDesktopHidden ? 0 : 1,
          pointerEvents: isMobile
            ? isMobileSidebarOpen
              ? "auto"
              : "none"
            : isDesktopHidden
              ? "none"
              : "auto",
          transform: isMobile
            ? isMobileSidebarOpen
              ? "translateX(0)"
              : "translateX(-110%)"
            : isDesktopHidden
              ? "translateX(-12px)"
              : "translateX(0)",
          transition:
            "width 220ms cubic-bezier(0.22, 1, 0.36, 1), min-width 220ms cubic-bezier(0.22, 1, 0.36, 1), opacity 180ms ease, transform 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        <ProSidebar
          collapsed={isDesktopCompact}
          width={`${desktopSidebarWidth}px`}
          collapsedWidth={`${desktopCompactSidebarWidth}px`}
          rootStyles={{
            height: "100vh",
            border: "none",
            color: mutedColor,
            [`.${sidebarClasses.container}`]: {
              background: sidebarBackground,
              borderRight: `1px solid ${alpha(
                theme.palette.mode === "dark" ? theme.palette.common.white : textColor,
                0.08
              )}`,
              overflowY: "auto",
              overflowX: "hidden",
              boxShadow: isMobile
                ? `0 20px 50px ${alpha(theme.palette.common.black, 0.45)}`
                : isDesktopCompact
                  ? `0 12px 28px ${alpha(theme.palette.common.black, 0.14)}`
                  : `0 18px 48px ${alpha(theme.palette.common.black, 0.18)}`,
            },
            [`.${menuClasses.root}`]: {
              overflowX: "hidden",
              maxWidth: "100%",
            },
            [`.${menuClasses.menuItemRoot}`]: {
              maxWidth: "100%",
              minWidth: 0,
              boxSizing: "border-box",
            },
            [`.${menuClasses.button}`]: {
              width: "100%",
              maxWidth: "100%",
              minWidth: 0,
              boxSizing: "border-box",
            },
            [`.${menuClasses.label}`]: {
              minWidth: 0,
              maxWidth: "100%",
            },
            [`.${menuClasses.subMenuContent}`]: {
              overflowX: "hidden !important",
              width: "100%",
              maxWidth: "100%",
              minWidth: 0,
              boxSizing: "border-box",
            },
            [`.${menuClasses.subMenuContent} > ul`]: {
              width: "100%",
              maxWidth: "100%",
              minWidth: 0,
              overflowX: "hidden",
            },
            [`.${menuClasses.subMenuContent} .${menuClasses.menuItemRoot}`]: {
              width: "100%",
              maxWidth: "100%",
              minWidth: 0,
            },
            [`.${menuClasses.subMenuContent} .${menuClasses.button}`]: {
              width: "100%",
              maxWidth: "100%",
              minWidth: 0,
            },
          }}
        >
          <Box px={isDesktopCompact ? "8px" : "14px"} pt="8px" pb={isDesktopCompact ? "6px" : "4px"}>
            <Box sx={{ px: isDesktopCompact ? 0 : 0.75, py: isDesktopCompact ? 0.5 : 0.75 }}>
              <Box display="flex" justifyContent="center">
                <Box
                  component="img"
                  alt="profile-user"
                  src={sidebarAvatarSrc}
                  title={isDesktopCompact ? user?.name || "Admin" : undefined}
                  sx={{
                    width: isDesktopCompact ? 40 : 60,
                    height: isDesktopCompact ? 40 : 60,
                    borderRadius: "50%",
                    objectFit: "cover",
                    flexShrink: 0,
                    border: `2px solid ${alpha(accentColor, 0.28)}`,
                    boxShadow: `0 10px 24px ${alpha(
                      theme.palette.mode === "dark"
                        ? theme.palette.common.black
                        : colorTokens.blueAccent[300],
                      0.16
                    )}`,
                  }}
                />
              </Box>
              {!isDesktopCompact ? (
                <Typography
                  color={textColor}
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
              ) : null}
            </Box>
          </Box>

          <Box px={isDesktopCompact ? "4px" : "6px"} pt="2px" pb="8px">
            <Menu closeOnClick={isDesktopCompact} menuItemStyles={menuItemStyles}>
              {canDashboard && (
                <Item
                  title="Dashboard"
                  to="/dashboard"
                  icon={<HomeOutlinedIcon />}
                  isActive={isActivePath("/dashboard")}
                  onClick={closeOnMobile}
                  isCompact={isDesktopCompact}
                />
              )}

              {(canContent || canAllChannels || canTraffic || canGeography || canAudience || canReach || canRevenue) && (
                <SubMenu
                  label={<Typography sx={subMenuTitleSx}>Analytics</Typography>}
                  icon={<BarChartOutlinedIcon />}
                  active={defaultOpenAnalytics}
                  defaultOpen={defaultOpenAnalytics}
                  title={isDesktopCompact ? "Analytics" : undefined}
                >
                  {canAllChannels && (
                    <Item
                      title="Overview"
                      to="/all_channels"
                      icon={<ViewModuleOutlinedIcon />}
                      isActive={isActivePath("/all_channels")}
                      onClick={closeOnMobile}
                      onMouseEnter={() => prefetchContentPage({ forceAllChannels: true })}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canContent && (
                    <Item
                      title="Content"
                      to="/content"
                      icon={<DatasetIcon />}
                      isActive={isActivePath("/content")}
                      onClick={closeOnMobile}
                      onMouseEnter={() => prefetchContentPage()}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canTraffic && (
                    <Item
                      title="Traffic Source"
                      to="/traffic_source"
                      icon={<DeviceUnknownIcon />}
                      isActive={isActivePath("/traffic_source")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canGeography && (
                    <Item
                      title="Geography Chart"
                      to="/geography"
                      icon={<MapOutlinedIcon />}
                      isActive={isActivePath("/geography")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canAudience && (
                    <Item
                      title="Audience"
                      to="/audience_analytics"
                      icon={<GroupsOutlinedIcon />}
                      isActive={isActivePath("/audience_analytics")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canReach && (
                    <Item
                      title="Reach"
                      to="/reach"
                      icon={<VisibilityOutlinedIcon />}
                      isActive={isActivePath("/reach")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canRevenue && (
                    <Item
                      title="Revenue"
                      to="/revenue"
                      icon={<AttachMoneyIcon />}
                      isActive={isActivePath("/revenue")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                </SubMenu>
              )}

              {(canChannelCompare || canRivals) && (
                <SubMenu
                  label={<Typography sx={subMenuTitleSx}>Statistics</Typography>}
                  icon={<QueryStatsIcon />}
                  active={defaultOpenStatistics}
                  defaultOpen={defaultOpenStatistics}
                  title={isDesktopCompact ? "Statistics" : undefined}
                >
                  {canChannelCompare && (
                    <Item
                      title="Channel Compare"
                      to="/channel_compare"
                      icon={<BarChartOutlinedIcon />}
                      isActive={isActivePath("/channel_compare")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canRivals && (
                    <Item
                      title="Rivals"
                      to="/rivals"
                      icon={<WebhookIcon />}
                      isActive={isActivePath("/rivals")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                </SubMenu>
              )}

              {canResearch && (
                <SubMenu
                  label={<Typography sx={subMenuTitleSx}>Report</Typography>}
                  icon={<TravelExploreOutlinedIcon />}
                  active={defaultOpenResearch}
                  defaultOpen={defaultOpenResearch}
                  title={isDesktopCompact ? "Report" : undefined}
                >
                  <Item
                    title="Summary"
                    to="/research/summary"
                    icon={<BarChartOutlinedIcon />}
                    isActive={pathname === "/research/summary"}
                    onClick={closeOnMobile}
                    isCompact={isDesktopCompact}
                  />
                  <Item
                    title="View"
                    to="/research"
                    icon={<BarChartOutlinedIcon />}
                    isActive={pathname === "/research"}
                    onClick={closeOnMobile}
                    isCompact={isDesktopCompact}
                  />
                  <Item
                    title="Seo"
                    to="/research/seo"
                    icon={<ManageSearchOutlinedIcon />}
                    isActive={pathname === "/research/seo"}
                    onClick={closeOnMobile}
                    isCompact={isDesktopCompact}
                  />
                </SubMenu>
              )}

              {(canSmmstore || canMail) && (
                <SubMenu
                  label={<Typography sx={subMenuTitleSx}>Automation</Typography>}
                  icon={<AutoModeIcon />}
                  active={defaultOpenAutomation}
                  defaultOpen={defaultOpenAutomation}
                  title={isDesktopCompact ? "Automation" : undefined}
                >
                  {canSmmstore && (
                    <Item
                      title="SMMStore Orders"
                      to="/smmstore"
                      icon={<AttachMoneyIcon />}
                      isActive={isActivePath("/smmstore")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canSmmstore && (
                    <Item
                      title="SMMStore Analytics"
                      to="/smmstore_analytics"
                      icon={<BarChartOutlinedIcon />}
                      isActive={isActivePath("/smmstore_analytics")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canMail && (
                    <Item
                      title="Email Manager"
                      to="/mail_monitor"
                      icon={<MailOutlineRoundedIcon />}
                      isActive={isActivePath("/mail_monitor")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                </SubMenu>
              )}

              {canConfig && (
                <SubMenu
                  label={<Typography sx={subMenuTitleSx}>Setting</Typography>}
                  icon={<SettingsOutlinedIcon />}
                  active={defaultOpenSettings}
                  defaultOpen={defaultOpenSettings}
                  title={isDesktopCompact ? "Setting" : undefined}
                >
                  <Item
                    title="Channel"
                    to="/config/channels"
                    icon={<SmartDisplayOutlinedIcon />}
                    isActive={isActivePath("/config/channels")}
                    onClick={closeOnMobile}
                    isCompact={isDesktopCompact}
                  />
                  {(canManageStructure || canManageRoles) && (
                    <Item
                      title="Permissions"
                      to="/config/project"
                      icon={<AccountTreeOutlinedIcon />}
                      isActive={isActivePath("/config/project")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canManageStructure && (
                    <Item
                      title="Schedule"
                      to="/config/schedule"
                      icon={<ScheduleOutlinedIcon />}
                      isActive={isActivePath("/config/schedule")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                  {canManageStructure && (
                    <Item
                      title="Run logs"
                      to="/config/logs"
                      icon={<HistoryOutlinedIcon />}
                      isActive={isActivePath("/config/logs")}
                      onClick={closeOnMobile}
                      isCompact={isDesktopCompact}
                    />
                  )}
                </SubMenu>
              )}
            </Menu>
          </Box>
        </ProSidebar>
      </Box>
    </>
  );
};

export default Sidebar;
