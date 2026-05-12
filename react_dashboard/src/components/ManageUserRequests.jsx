import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  Tooltip,
  Typography,
  useTheme,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import {
  deleteAdminUser,
  listAdminUsers,
  resetAdminUserPassword,
  updateAdminUserRole,
} from "../services/userService";
import { getApiBase } from "../config";

const ManageUserRequests = ({ active = false }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const primary = theme.palette.primary.main;
  const secondary = theme.palette.secondary?.main || theme.palette.primary.main;
  const userBlue = "#3b82f6";
  const errorMain = theme.palette.error.main;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [passwordDrafts, setPasswordDrafts] = useState({});
  const [editingPasswordUserId, setEditingPasswordUserId] = useState(null);
  const [menuAnchorEl, setMenuAnchorEl] = useState(null);
  const [menuUser, setMenuUser] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listAdminUsers();
      const nextItems = Array.isArray(data?.items) ? data.items : [];
      setItems(nextItems);
      setPasswordDrafts((prev) => {
        const next = { ...prev };
        nextItems.forEach((item) => {
          if (typeof next[item.id] !== "string") {
            next[item.id] = "";
          }
        });
        return next;
      });
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

  const resolveAvatarSrc = (value) => {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (/^https?:\/\//i.test(raw)) return raw;
    const base = getApiBase() || "";
    const cleanBase = base.endsWith("/") ? base.slice(0, -1) : base;
    const cleanRaw = raw.startsWith("/") ? raw : `/${raw}`;
    return `${cleanBase}${cleanRaw}`;
  };

  const handleResetPassword = async (item) => {
    const nextPassword = String(passwordDrafts[item.id] || "").trim();
    if (!nextPassword) {
      setError("Enter a new password before resetting.");
      return;
    }
    setBusyKey(`reset:${item.id}`);
    setError("");
    try {
      await resetAdminUserPassword(item.id, nextPassword);
      setPasswordDrafts((prev) => ({ ...prev, [item.id]: "" }));
      setEditingPasswordUserId((prev) => (prev === item.id ? null : prev));
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to reset password.");
    } finally {
      setBusyKey("");
    }
  };

  const handleToggleAdmin = async (item) => {
    setBusyKey(`role:${item.id}`);
    setError("");
    try {
      await updateAdminUserRole(item.id, !item.is_admin);
      await loadUsers();
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

  const confirmDeleteUser = async () => {
    const item = userToDelete;
    if (!item) return;
    
    setDeleteConfirmOpen(false);
    setBusyKey(`delete:${item.id}`);
    setError("");
    try {
      await deleteAdminUser(item.id);
      await loadUsers();
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
            const resetBusy = busyKey === `reset:${item.id}`;
            const deleteBusy = busyKey === `delete:${item.id}`;
            const isEditingPassword = editingPasswordUserId === item.id;
            const isAdmin = !!item.is_admin;
            const accentColor = isAdmin ? secondary : primary;
            const avatarBorderColor = isAdmin ? secondary : userBlue;

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
                  <Tooltip title="Edit Password">
                    <IconButton
                      size="small"
                      onClick={() =>
                        setEditingPasswordUserId((prev) => (prev === item.id ? null : item.id))
                      }
                      sx={{
                        color: isDark ? "#94a3b8" : "text.secondary",
                        bgcolor: alpha(theme.palette.background.default, 0.5),
                        "&:hover": {
                          color: isAdmin ? secondary : userBlue,
                          bgcolor: alpha(isAdmin ? secondary : userBlue, 0.1),
                        },
                      }}
                    >
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
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
                    label={isAdmin ? "Admin" : "User"}
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

                {/* Password Edit Section */}
                {isEditingPassword && (
                  <Box
                    sx={{
                      width: "100%",
                      mt: 1,
                      pt: 1,
                      animation: "fadeIn 0.3s ease-out",
                      "@keyframes fadeIn": {
                        from: { opacity: 0, transform: "translateY(-10px)" },
                        to: { opacity: 1, transform: "translateY(0)" },
                      },
                    }}
                  >
                    <TextField
                      fullWidth
                      size="small"
                      type="password"
                      placeholder="New password"
                      value={passwordDrafts[item.id] || ""}
                      onChange={(event) =>
                        setPasswordDrafts((prev) => ({
                          ...prev,
                          [item.id]: event.target.value,
                        }))
                      }
                      sx={{
                        "& .MuiOutlinedInput-root": {
                          borderRadius: 2,
                          bgcolor: isDark ? alpha(theme.palette.common.black, 0.2) : alpha(theme.palette.common.white, 0.5),
                        },
                      }}
                    />
                    <Button
                      fullWidth
                      variant="contained"
                      onClick={() => handleResetPassword(item)}
                      disabled={resetBusy || !passwordDrafts[item.id]}
                      sx={{
                        mt: 1.5,
                        borderRadius: 2,
                        textTransform: "none",
                        fontWeight: 700,
                        bgcolor: isAdmin ? secondary : userBlue,
                        boxShadow: `0 4px 12px ${alpha(isAdmin ? secondary : userBlue, 0.3)}`,
                        "&:hover": {
                          bgcolor: isAdmin ? secondary : userBlue,
                          boxShadow: `0 6px 16px ${alpha(isAdmin ? secondary : userBlue, 0.4)}`,
                        },
                      }}
                    >
                      {resetBusy ? "Updating..." : "Update Password"}
                    </Button>
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>
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
    </Box>
  );
};

export default ManageUserRequests;
