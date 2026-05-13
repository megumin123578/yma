import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  IconButton,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
  useTheme,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import CheckBoxOutlineBlankIcon from "@mui/icons-material/CheckBoxOutlineBlank";
import CheckBoxIcon from "@mui/icons-material/CheckBox";
import { alpha } from "@mui/material/styles";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import AdminPanelSettingsOutlinedIcon from "@mui/icons-material/AdminPanelSettingsOutlined";
import {
  deleteAdminUser,
  getAdminUserRoles,
  listAdminUsers,
  listRoles,
  setAdminUserRoles,
  updateAdminUserRole,
} from "../services/userService";
import { getApiBase } from "../config";

const ManageUserRequests = ({
  active = false,
  compact = false,
  selectedUserId = null,
  onSelectUser,
  highlightedUserIds,
  onUsersChanged,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const primary = theme.palette.primary.main;
  const secondary = theme.palette.secondary?.main || theme.palette.primary.main;
  const userBlue = "#3b82f6";
  const errorMain = theme.palette.error.main;
  const highlightedUserSet = useMemo(
    () => new Set(highlightedUserIds || []),
    [highlightedUserIds]
  );
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [menuUser, setMenuUser] = useState(null);
  const [allRoles, setAllRoles] = useState([]);
  const [rolesMenuAnchor, setRolesMenuAnchor] = useState(null);
  const [rolesMenuUser, setRolesMenuUser] = useState(null);
  const [rolesMenuSelected, setRolesMenuSelected] = useState([]);
  const [rolesMenuOriginal, setRolesMenuOriginal] = useState([]);
  const [rolesMenuLoading, setRolesMenuLoading] = useState(false);
  const [rolesMenuSaving, setRolesMenuSaving] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listAdminUsers();
      const nextItems = (Array.isArray(data?.items) ? data.items : [])
        .slice()
        .sort((a, b) => (b.is_admin ? 1 : 0) - (a.is_admin ? 1 : 0));
      setItems(nextItems);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to load users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!active) return;
    loadUsers();
  }, [active, loadUsers]);

  useEffect(() => {
    if (!active) return;
    const handler = () => loadUsers();
    window.addEventListener("roles-data-changed", handler);
    return () => window.removeEventListener("roles-data-changed", handler);
  }, [active, loadUsers]);

  const resolveAvatarSrc = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) return raw;
    const base = getApiBase() || "";
    const cleanBase = base.endsWith("/") ? base.slice(0, -1) : base;
    const cleanRaw = raw.startsWith("/") ? raw : `/${raw}`;
    return `${cleanBase}${cleanRaw}`;
  };

  const handleToggleAdmin = async (item) => {
    setBusyKey(`role:${item.id}`);
    setError("");
    try {
      await updateAdminUserRole(item.id, !item.is_admin);
      await loadUsers();
      onUsersChanged?.();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to update admin role.");
    } finally {
      setBusyKey("");
    }
  };

  const handleDeleteUser = (item) => {
    setUserToDelete(item);
    setDeleteConfirmOpen(true);
  };

  const loadAllRoles = useCallback(async () => {
    try {
      const data = await listRoles();
      setAllRoles(Array.isArray(data?.items) ? data.items : []);
    } catch {
      setAllRoles([]);
    }
  }, []);

  const openRolesMenu = async (event, item) => {
    event.stopPropagation();
    setRolesMenuAnchor(event.currentTarget);
    setRolesMenuUser(item);
    setRolesMenuLoading(true);
    setError("");
    try {
      const [, roleData] = await Promise.all([
        loadAllRoles(),
        getAdminUserRoles(item.id),
      ]);
      const ids = (roleData?.roles || []).map((r) => r.id);
      setRolesMenuSelected(ids);
      setRolesMenuOriginal(ids);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to load user roles.");
      setRolesMenuAnchor(null);
      setRolesMenuUser(null);
    } finally {
      setRolesMenuLoading(false);
    }
  };

  const toggleRoleInMenu = (roleId) => {
    setRolesMenuSelected((prev) =>
      prev.includes(roleId)
        ? prev.filter((id) => id !== roleId)
        : [...prev, roleId]
    );
  };

  const closeRolesMenu = async () => {
    if (rolesMenuSaving) return;
    const user = rolesMenuUser;
    const next = rolesMenuSelected;
    const orig = rolesMenuOriginal;
    const changed =
      next.length !== orig.length || next.some((id) => !orig.includes(id));
    setRolesMenuAnchor(null);
    if (!changed || !user) {
      setRolesMenuUser(null);
      setRolesMenuSelected([]);
      setRolesMenuOriginal([]);
      return;
    }
    setRolesMenuSaving(true);
    setError("");
    try {
      await setAdminUserRoles(user.id, next);
      await loadUsers();
      onUsersChanged?.();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to update roles.");
    } finally {
      setRolesMenuSaving(false);
      setRolesMenuUser(null);
      setRolesMenuSelected([]);
      setRolesMenuOriginal([]);
    }
  };

  const confirmDeleteUser = async () => {
    const item = userToDelete;
    if (!item) return;
    
    setDeleteConfirmOpen(false);
    setBusyKey(`delete:${item.id}`);
    setError("");
    try {
      await deleteAdminUser(item.id);
      await loadUsers();
      onUsersChanged?.();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete user.");
    } finally {
      setBusyKey("");
      setUserToDelete(null);
    }
  };

  const openActionsMenu = (event, item) => {
    setMenuAnchorEl(event.currentTarget);
    setMenuUser(item);
  };

  const closeActionsMenu = () => {
    setMenuAnchorEl(null);
    setMenuUser(null);
  };

  return (
    <Box>
      {error && (
        <Alert
          severity="error"
          sx={{
            mb: 3,
            borderRadius: 2,
            bgcolor: alpha(errorMain, 0.1),
            color: errorMain,
            border: `1px solid ${alpha(errorMain, 0.2)}`,
            "& .MuiAlert-icon": { color: errorMain },
          }}
        >
          {error}
        </Alert>
      )}

      {loading ? (
        <Box display="flex" justifyContent="center" py={8}>
          <CircularProgress
            size={40}
            thickness={4}
            sx={{
              color: primary,
              filter: "drop-shadow(0 0 8px rgba(144,202,249,0.5))",
            }}
          />
        </Box>
      ) : items.length ? (
        compact ? (
        <Box display="flex" flexDirection="column" gap={1}>
          {items.map((item) => {
            const deleteBusy = busyKey === `delete:${item.id}`;
            const isAdmin = !!item.is_admin;
            const isOwner = !!item.is_owner;
            const assignedRoles = Array.isArray(item.roles) ? item.roles : [];
            const noRoleColor = isDark ? "#94a3b8" : "#64748b";
            const accentColor = isOwner
              ? "#f59e0b"
              : isAdmin
                ? secondary
                : assignedRoles[0]?.color || userBlue;
            const isSelected = selectedUserId === item.id;
            const isHighlighted = highlightedUserSet.has(item.id);
            const canSelect = !isAdmin && !!onSelectUser;
            const handleRowClick = () => {
              if (canSelect) onSelectUser(item);
            };
            return (
              <Box key={item.id}>
                <Box
                  onClick={handleRowClick}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1.25,
                    p: 1,
                    borderRadius: 2,
                    cursor: canSelect ? "pointer" : "default",
                    border: `1px solid ${
                      isSelected
                        ? accentColor
                        : isHighlighted
                          ? alpha(accentColor, 0.5)
                          : alpha(isDark ? "#ffffff" : "#000000", 0.08)
                    }`,
                    bgcolor: isSelected
                      ? alpha(accentColor, 0.14)
                      : isHighlighted
                        ? alpha(accentColor, 0.06)
                        : "transparent",
                    transition: "all 0.15s",
                    "&:hover": canSelect
                      ? { bgcolor: alpha(accentColor, 0.09) }
                      : {},
                  }}
                >
                  <Box sx={{ position: "relative" }}>
                    <Avatar
                      src={resolveAvatarSrc(item.avatar_url)}
                      alt={item.name || item.username}
                      sx={{
                        width: 40,
                        height: 40,
                        fontSize: 16,
                        fontWeight: 800,
                        bgcolor: alpha(accentColor, 0.15),
                        color: accentColor,
                        border: `2px solid ${alpha(accentColor, 0.3)}`,
                      }}
                    >
                      {(item.name || item.username || "?")
                        .slice(0, 1)
                        .toUpperCase()}
                    </Avatar>
                    <Box
                      sx={{
                        position: "absolute",
                        bottom: -2,
                        right: -2,
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        bgcolor:
                          item.is_active !== false ? "#10b981" : "#94a3b8",
                        border: `2px solid ${isDark ? "#1e293b" : "#ffffff"}`,
                      }}
                    />
                  </Box>
                  <Box sx={{ minWidth: 0, flex: 1 }}>
                    <Typography
                      variant="body2"
                      noWrap
                      sx={{
                        fontWeight: 700,
                        color: isDark ? "#f8fafc" : "#1e293b",
                      }}
                    >
                      {item.name || item.username}
                    </Typography>
                    <Box
                      sx={{
                        mt: 0.25,
                        display: "flex",
                        flexWrap: "wrap",
                        gap: 0.5,
                      }}
                    >
                      {isOwner && (
                        <Chip
                          label="Owner"
                          size="small"
                          sx={{
                            height: 18,
                            fontSize: "0.6rem",
                            fontWeight: 800,
                            letterSpacing: "0.08em",
                            bgcolor: alpha("#f59e0b", 0.12),
                            color: "#f59e0b",
                            border: `1px solid ${alpha("#f59e0b", 0.3)}`,
                            "& .MuiChip-label": { px: 0.75 },
                          }}
                        />
                      )}
                      {!isOwner && isAdmin && (
                        <Chip
                          label="Admin"
                          size="small"
                          clickable
                          onClick={(event) => {
                            event.stopPropagation();
                            openActionsMenu(event, item);
                          }}
                          sx={{
                            height: 18,
                            fontSize: "0.6rem",
                            fontWeight: 800,
                            letterSpacing: "0.08em",
                            bgcolor: alpha(secondary, 0.12),
                            color: secondary,
                            border: `1px solid ${alpha(secondary, 0.3)}`,
                            "& .MuiChip-label": { px: 0.75 },
                          }}
                        />
                      )}
                      {assignedRoles.map((role) => {
                        const roleColor = role.color || userBlue;
                        return (
                          <Chip
                            key={role.id}
                            label={role.name}
                            size="small"
                            sx={{
                              height: 18,
                              fontSize: "0.6rem",
                              fontWeight: 800,
                              letterSpacing: "0.08em",
                              bgcolor: alpha(roleColor, 0.12),
                              color: roleColor,
                              border: `1px solid ${alpha(roleColor, 0.3)}`,
                              "& .MuiChip-label": { px: 0.75 },
                            }}
                          />
                        );
                      })}
                      {!isOwner && !isAdmin && assignedRoles.length === 0 && (
                        <Chip
                          label="No role"
                          size="small"
                          sx={{
                            height: 18,
                            fontSize: "0.6rem",
                            fontWeight: 800,
                            letterSpacing: "0.08em",
                            bgcolor: alpha(noRoleColor, 0.12),
                            color: noRoleColor,
                            border: `1px solid ${alpha(noRoleColor, 0.3)}`,
                            "& .MuiChip-label": { px: 0.75 },
                          }}
                        />
                      )}
                    </Box>
                  </Box>
                  <Box
                    sx={{ display: "flex", gap: 0.5 }}
                    onClick={(event) => event.stopPropagation()}
                  >
                    <Tooltip title="Assign roles">
                      <IconButton
                        size="small"
                        onClick={(event) => openRolesMenu(event, item)}
                        sx={{
                          color: isDark ? "#94a3b8" : "text.secondary",
                          "&:hover": {
                            color: accentColor,
                            bgcolor: alpha(accentColor, 0.1),
                          },
                        }}
                      >
                        <AdminPanelSettingsOutlinedIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    {!isOwner && (
                      <Tooltip title="Delete User">
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteUser(item)}
                          disabled={deleteBusy}
                          sx={{
                            color: isDark ? "#94a3b8" : "text.secondary",
                            "&:hover": {
                              color: errorMain,
                              bgcolor: alpha(errorMain, 0.1),
                            },
                          }}
                        >
                          {deleteBusy ? (
                            <CircularProgress size={14} color="inherit" />
                          ) : (
                            <DeleteOutlineIcon fontSize="small" />
                          )}
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
              </Box>
            );
          })}
        </Box>
        ) : (
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: {
              xs: "1fr",
              sm: "repeat(auto-fill, minmax(260px, 1fr))",
              lg: "repeat(auto-fill, minmax(280px, 1fr))",
            },
            gap: 3,
            px: 0.5,
          }}
        >
          {items.map((item) => {
            const deleteBusy = busyKey === `delete:${item.id}`;
            const isAdmin = !!item.is_admin;
            const isOwner = !!item.is_owner;
            const accentColor = isOwner ? "#f59e0b" : isAdmin ? secondary : primary;
            const avatarBorderColor = isOwner ? "#f59e0b" : isAdmin ? secondary : userBlue;
            const roleLabel = isOwner ? "Owner" : isAdmin ? "Admin" : "User";

            return (
              <Box
                key={item.id}
                sx={{
                  position: "relative",
                  borderRadius: 4,
                  p: 3,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 2,
                  transition: "none",
                  bgcolor: theme.palette.background.paper,
                  backgroundImage: "none",
                  border: `1px solid ${alpha(accentColor, 0.2)}`,
                  boxShadow: isDark
                    ? `0 10px 30px ${alpha(theme.palette.common.black, 0.3)}`
                    : `0 10px 30px ${alpha(accentColor, 0.1)}`,
                  backdropFilter: "blur(10px)",
                  WebkitBackdropFilter: "blur(10px)",
                }}
              >
                {/* Action Buttons Overlay */}
                <Box
                  sx={{
                    position: "absolute",
                    top: 12,
                    right: 12,
                    display: "flex",
                    gap: 1,
                    opacity: 0.6,
                    transition: "opacity 0.2s",
                    "&:hover": { opacity: 1 },
                  }}
                >
                  <Tooltip title="Assign roles">
                    <IconButton
                      size="small"
                      onClick={(event) => openRolesMenu(event, item)}
                      sx={{
                        color: isDark ? "#94a3b8" : "text.secondary",
                        bgcolor: alpha(theme.palette.background.default, 0.5),
                        "&:hover": {
                          color: isAdmin ? secondary : userBlue,
                          bgcolor: alpha(isAdmin ? secondary : userBlue, 0.1),
                        },
                      }}
                    >
                      <AdminPanelSettingsOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  {!isOwner && (
                    <Tooltip title="Delete User">
                      <IconButton
                        size="small"
                        onClick={() => handleDeleteUser(item)}
                        disabled={deleteBusy}
                        sx={{
                          color: isDark ? "#94a3b8" : "text.secondary",
                          bgcolor: alpha(theme.palette.background.default, 0.5),
                          "&:hover": {
                            color: errorMain,
                            bgcolor: alpha(errorMain, 0.1),
                          },
                        }}
                      >
                        {deleteBusy ? (
                          <CircularProgress size={18} color="inherit" />
                        ) : (
                          <DeleteOutlineIcon fontSize="small" />
                        )}
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>

                {/* Avatar Section */}
                <Box sx={{ position: "relative" }}>
                  <Avatar
                    src={resolveAvatarSrc(item.avatar_url)}
                    alt={item.name || item.username}
                    sx={{
                      width: 90,
                      height: 90,
                      fontSize: 32,
                      fontWeight: 800,
                      bgcolor: alpha(avatarBorderColor, 0.15),
                      color: avatarBorderColor,
                      border: `3px solid ${alpha(avatarBorderColor, 0.3)}`,
                      boxShadow: `0 0 20px ${alpha(avatarBorderColor, 0.2)}`,
                    }}
                  >
                    {(item.name || item.username || "?").slice(0, 1).toUpperCase()}
                  </Avatar>
                  <Box
                    sx={{
                      position: "absolute",
                      bottom: 0,
                      right: 0,
                      width: 24,
                      height: 24,
                      borderRadius: "50%",
                      bgcolor: item.is_active !== false ? "#10b981" : "#94a3b8",
                      border: `4px solid ${isDark ? "#1e293b" : "#ffffff"}`,
                      boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                    }}
                  />
                </Box>

                {/* Info Section */}
                <Box textAlign="center" sx={{ width: "100%" }}>
                  <Typography
                    variant="h6"
                    sx={{
                      fontWeight: 800,
                      color: isDark ? "#f8fafc" : "#1e293b",
                      mb: 0.5,
                      textOverflow: "ellipsis",
                      overflow: "hidden",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {item.name || item.username}
                  </Typography>
                  <Box sx={{ mb: 1.5 }} />

                  <Chip
                    label={roleLabel}
                    clickable
                    onClick={(event) => openActionsMenu(event, item)}
                    sx={{
                      height: 28,
                      px: 1,
                      fontWeight: 800,
                      fontSize: "0.65rem",
                      letterSpacing: "0.1em",
                      bgcolor: alpha(isAdmin ? secondary : userBlue, 0.1),
                      color: isAdmin ? secondary : userBlue,
                      border: `1px solid ${alpha(isAdmin ? secondary : userBlue, 0.3)}`,
                      transition: "all 0.2s",
                      "&:hover": {
                        bgcolor: alpha(isAdmin ? secondary : userBlue, 0.2),
                        transform: "scale(1.05)",
                      },
                    }}
                  />
                </Box>

              </Box>
            );
          })}
        </Box>
        )
      ) : (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            py: 10,
            opacity: 0.6,
          }}
        >
          <Typography variant="body1">No users found.</Typography>
        </Box>
      )}

      {/* Role Menu */}
      <Menu
        anchorEl={menuAnchorEl}
        open={!!menuAnchorEl}
        onClose={closeActionsMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
        transformOrigin={{ vertical: "top", horizontal: "center" }}
        PaperProps={{
          elevation: 8,
          sx: {
            mt: 1.5,
            minWidth: 180,
            borderRadius: 3,
            border: `1px solid ${isDark ? alpha("#ffffff", 0.15) : alpha(primary, 0.1)}`,
            bgcolor: isDark ? "#0f172a" : "#ffffff",
            backgroundImage: "none",
            backdropFilter: "blur(12px)",
            boxShadow: isDark 
              ? `0 10px 40px ${alpha("#000000", 0.6)}`
              : "0 10px 40px rgba(0,0,0,0.1)",
            p: 1,
          },
        }}
      >
        <MenuItem
          onClick={async () => {
            const current = menuUser;
            closeActionsMenu();
            if (current && !current.is_admin) await handleToggleAdmin(current);
          }}
          sx={{
            borderRadius: 2,
            mb: 0.5,
            fontWeight: 700,
            fontSize: "0.85rem",
            color: secondary,
            bgcolor: menuUser?.is_admin ? alpha(secondary, 0.1) : "transparent",
            "&:hover": { bgcolor: alpha(secondary, 0.15) },
          }}
        >
          Admin
        </MenuItem>
        <MenuItem
          onClick={async () => {
            const current = menuUser;
            closeActionsMenu();
            if (current && current.is_admin) await handleToggleAdmin(current);
          }}
          sx={{
            borderRadius: 2,
            fontWeight: 700,
            fontSize: "0.85rem",
            color: userBlue,
            bgcolor: menuUser && !menuUser.is_admin ? alpha(userBlue, 0.1) : "transparent",
            "&:hover": { bgcolor: alpha(userBlue, 0.15) },
          }}
        >
          User
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        maxWidth="xs"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 3,
            bgcolor: isDark ? "#1e293b" : "#ffffff",
            backgroundImage: "none",
            boxShadow: isDark ? "0 20px 50px rgba(0,0,0,0.5)" : "0 10px 30px rgba(0,0,0,0.1)",
          },
        }}
      >
        <DialogTitle sx={{ fontWeight: 800, pt: 3 }}>Confirm Deletion</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ color: isDark ? "#94a3b8" : "text.secondary" }}>
            Are you sure you want to delete user{" "}
            <Box component="span" sx={{ color: isDark ? "#f8fafc" : "#1e293b", fontWeight: 700 }}>
              {userToDelete?.name || userToDelete?.username}
            </Box>
            ? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ p: 3, pt: 1 }}>
          <Button
            onClick={() => setDeleteConfirmOpen(false)}
            sx={{
              color: isDark ? "#94a3b8" : "text.secondary",
              textTransform: "none",
              fontWeight: 700,
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={confirmDeleteUser}
            sx={{
              borderRadius: 2,
              textTransform: "none",
              fontWeight: 700,
              px: 3,
              boxShadow: `0 4px 12px ${alpha(errorMain, 0.3)}`,
              "&:hover": {
                bgcolor: errorMain,
                boxShadow: `0 6px 16px ${alpha(errorMain, 0.4)}`,
              },
            }}
          >
            Delete User
          </Button>
        </DialogActions>
      </Dialog>

      <Menu
        anchorEl={rolesMenuAnchor}
        open={Boolean(rolesMenuAnchor)}
        onClose={closeRolesMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        PaperProps={{
          sx: {
            mt: 0.5,
            minWidth: 260,
            maxHeight: 360,
            borderRadius: 2,
            bgcolor: isDark ? "#0f172a" : "#ffffff",
            backgroundImage: "none",
          },
        }}
      >
        {rolesMenuLoading ? (
          <Box display="flex" justifyContent="center" py={2}>
            <CircularProgress size={20} />
          </Box>
        ) : allRoles.length === 0 ? (
          <MenuItem disabled sx={{ fontSize: "0.85rem" }}>
            No roles defined yet.
          </MenuItem>
        ) : (
          allRoles.map((r) => {
            const checked = rolesMenuSelected.includes(r.id);
            return (
              <MenuItem
                key={r.id}
                onClick={() => toggleRoleInMenu(r.id)}
                disabled={rolesMenuSaving}
                sx={{ gap: 1, py: 0.5 }}
              >
                <Checkbox
                  size="small"
                  icon={<CheckBoxOutlineBlankIcon fontSize="small" />}
                  checkedIcon={<CheckBoxIcon fontSize="small" />}
                  checked={checked}
                  sx={{ p: 0.5 }}
                  tabIndex={-1}
                />
                <Box
                  sx={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    bgcolor: r.color || "#94a3b8",
                    flexShrink: 0,
                  }}
                />
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography variant="body2" noWrap sx={{ fontWeight: 700 }}>
                    {r.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {r.member_count} member{r.member_count === 1 ? "" : "s"}
                    {r.is_system ? " · system" : ""}
                  </Typography>
                </Box>
              </MenuItem>
            );
          })
        )}
      </Menu>
    </Box>
  );
};

export default ManageUserRequests;
