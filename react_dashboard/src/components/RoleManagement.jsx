import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  IconButton,
  MenuItem,
  Select,
  TextField,
  Tooltip,
  Typography,
  useTheme,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import { Reorder, AnimatePresence } from "framer-motion";
import AddIcon from "@mui/icons-material/Add";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import {
  ADMIN_ACTIONS,
  DATA_ACTIONS,
  PAGE_ACTIONS,
  SCOPE_TYPES,
} from "../constants/permissions";
import {
  createRole,
  deleteRole,
  listRoles,
  setRolePermissions,
  updateRole,
} from "../services/userService";

const ROLE_COLORS = [
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#64748b",
];

const permKey = (p) => `${p.action}|${p.scope_type}|${p.scope_value || ""}`;

const RoleManagement = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const border = isDark ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.08)";
  const surface = isDark ? "rgba(15,23,42,0.5)" : "#ffffff";

  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [savingMeta, setSavingMeta] = useState(false);
  const [savingPerms, setSavingPerms] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [nameDraft, setNameDraft] = useState("");
  const [colorDraft, setColorDraft] = useState("");
  const [isDefaultDraft, setIsDefaultDraft] = useState(false);
  const [permsDraft, setPermsDraft] = useState([]);

  const [reordering, setReordering] = useState(false);

  const loadRolesList = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listRoles();
      const items = Array.isArray(data?.items) ? data.items : [];
      setRoles(items);
      setSelectedRoleId((prev) => {
        if (prev && items.some((r) => r.id === prev)) return prev;
        return items[0]?.id || null;
      });
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to load roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRolesList();
  }, [loadRolesList]);

  const selectedRole = useMemo(
    () => roles.find((r) => r.id === selectedRoleId) || null,
    [roles, selectedRoleId]
  );

  useEffect(() => {
    if (!selectedRole) {
      setNameDraft("");
      setColorDraft("");
      setIsDefaultDraft(false);
      setPermsDraft([]);
      return;
    }
    setNameDraft(selectedRole.name || "");
    setColorDraft(selectedRole.color || "");
    setIsDefaultDraft(!!selectedRole.is_default);
    setPermsDraft(
      (selectedRole.permissions || []).map((p) => ({
        action: p.action,
        scope_type: p.scope_type || "*",
        scope_value: p.scope_value || "",
      }))
    );
  }, [selectedRole]);

  const isSystemRole = !!selectedRole?.is_system;

  const handleCreateRole = async () => {
    setCreating(true);
    setError("");
    try {
      const data = await createRole({
        name: `New role ${roles.length + 1}`,
        color: ROLE_COLORS[roles.length % ROLE_COLORS.length],
        position: 0,
      });
      await loadRolesList();
      setSelectedRoleId(data?.role?.id || null);
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to create role.");
    } finally {
      setCreating(false);
    }
  };

  const handleSaveMeta = async () => {
    if (!selectedRole) return;
    setSavingMeta(true);
    setError("");
    try {
      await updateRole(selectedRole.id, {
        name: nameDraft.trim(),
        color: colorDraft || null,
        is_default: isDefaultDraft,
      });
      await loadRolesList();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to update role.");
    } finally {
      setSavingMeta(false);
    }
  };

  const handleSavePerms = async () => {
    if (!selectedRole || isSystemRole) return;
    setSavingPerms(true);
    setError("");
    try {
      await setRolePermissions(selectedRole.id, permsDraft);
      await loadRolesList();
    } catch (err) {
      setError(
        err?.response?.data?.detail || "Failed to update permissions."
      );
    } finally {
      setSavingPerms(false);
    }
  };

  const handleDeleteRole = async () => {
    if (!selectedRole || isSystemRole) return;
    setDeletingId(selectedRole.id);
    setError("");
    try {
      await deleteRole(selectedRole.id);
      setConfirmDelete(false);
      setSelectedRoleId(null);
      await loadRolesList();
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to delete role.");
    } finally {
      setDeletingId(null);
    }
  };

  // ---- Permission helpers ----

  const hasGlobalPerm = (action) =>
    permsDraft.some(
      (p) => p.action === action && p.scope_type === "*"
    );

  const togglePerm = (action, checked) => {
    setPermsDraft((prev) => {
      const filtered = prev.filter(
        (p) => !(p.action === action && p.scope_type === "*")
      );
      if (checked) {
        return [...filtered, { action, scope_type: "*", scope_value: "" }];
      }
      return filtered;
    });
  };

  const scopedRows = (action) =>
    permsDraft
      .map((p, idx) => ({ ...p, idx }))
      .filter((p) => p.action === action && p.scope_type !== "*");

  const addScopedRow = (action) => {
    setPermsDraft((prev) => [
      ...prev,
      { action, scope_type: "project", scope_value: "" },
    ]);
  };

  const updateScopedRow = (origIdx, field, value) => {
    setPermsDraft((prev) =>
      prev.map((p, idx) => (idx === origIdx ? { ...p, [field]: value } : p))
    );
  };

  const removeScopedRow = (origIdx) => {
    setPermsDraft((prev) => prev.filter((_, idx) => idx !== origIdx));
  };

  // ---- Drag-to-reorder ----

  const persistOrder = async (ordered) => {
    const previousRoles = roles;
    const N = ordered.length;
    const repositioned = ordered.map((r, i) => ({ ...r, position: N - i }));
    setRoles(repositioned);
    const changed = repositioned.filter((r) => {
      const original = previousRoles.find((o) => o.id === r.id);
      return !original || original.position !== r.position;
    });
    if (!changed.length) return;
    setReordering(true);
    setError("");
    try {
      await Promise.all(
        changed.map((r) => updateRole(r.id, { position: r.position }))
      );
    } catch (err) {
      setError(err?.response?.data?.detail || "Failed to save order.");
      loadRolesList();
    } finally {
      setReordering(false);
    }
  };

  const handleReorder = (next) => {
    setRoles(next);
  };

  const handleReorderEnd = (role) => {
    persistOrder(roles);
  };

  // ---- Render ----

  return (
    <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", md: "row" }, alignItems: "stretch" }}>
      <Box
        sx={{
          width: { xs: "100%", md: 320 },
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: 1,
        }}
      >
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
            Roles
          </Typography>
          <Button
            size="small"
            startIcon={<AddIcon />}
            onClick={handleCreateRole}
            disabled={creating}
            sx={{ textTransform: "none", fontWeight: 700 }}
          >
            {creating ? "Creating..." : "Create"}
          </Button>
        </Box>

        {loading ? (
          <Box display="flex" justifyContent="center" py={3}>
            <CircularProgress size={24} />
          </Box>
        ) : roles.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No roles yet.
          </Typography>
        ) : (
          <Reorder.Group
            axis="y"
            values={roles}
            onReorder={handleReorder}
            as="div"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 6,
              padding: 0,
              margin: 0,
              listStyle: "none",
            }}
          >
            <AnimatePresence initial={false}>
              {roles.map((r) => {
                const active = r.id === selectedRoleId;
                const color = r.color || "#94a3b8";
                return (
                  <Reorder.Item
                    key={r.id}
                    value={r}
                    as="div"
                    layout
                    onDragEnd={() => handleReorderEnd(r)}
                    whileDrag={{
                      scale: 1.03,
                      boxShadow: `0 18px 38px ${alpha("#000000", isDark ? 0.55 : 0.18)}`,
                      cursor: "grabbing",
                      zIndex: 5,
                    }}
                    transition={{
                      type: "spring",
                      stiffness: 380,
                      damping: 32,
                      mass: 0.6,
                    }}
                    onClick={() => setSelectedRoleId(r.id)}
                    style={{ borderRadius: 14, listStyle: "none" }}
                  >
                    <Box
                      sx={{
                        px: 1.25,
                        py: 1,
                        borderRadius: 1.75,
                        cursor: "grab",
                        border: `1px solid ${active ? color : border}`,
                        bgcolor: active ? alpha(color, 0.12) : surface,
                        display: "flex",
                        alignItems: "center",
                        gap: 1,
                        userSelect: "none",
                        "&:hover": { bgcolor: alpha(color, 0.08) },
                        "&:active": { cursor: "grabbing" },
                      }}
                    >
                      <DragIndicatorIcon
                        fontSize="small"
                        sx={{ color: "text.disabled", flexShrink: 0 }}
                      />
                      <Box
                        sx={{
                          width: 12,
                          height: 12,
                          borderRadius: "50%",
                          bgcolor: color,
                          flexShrink: 0,
                        }}
                      />
                      <Box sx={{ flex: 1, minWidth: 0 }}>
                        <Typography variant="body2" noWrap sx={{ fontWeight: 700 }}>
                          {r.name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {r.member_count} member{r.member_count === 1 ? "" : "s"}
                          {r.is_default ? " · default" : ""}
                          {r.is_system ? " · system" : ""}
                        </Typography>
                      </Box>
                    </Box>
                  </Reorder.Item>
                );
              })}
            </AnimatePresence>
            {reordering && (
              <Typography variant="caption" color="text.secondary" sx={{ pl: 1, mt: 0.5 }}>
                Saving order...
              </Typography>
            )}
          </Reorder.Group>
        )}
      </Box>

      <Box sx={{ flex: 1, minWidth: 0 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!selectedRole ? (
          <Typography variant="body2" color="text.secondary">
            Select a role on the left to edit.
          </Typography>
        ) : (
          <Box display="flex" flexDirection="column" gap={2.5}>
            {/* Meta */}
            <Box
              sx={{
                p: 2,
                border: `1px solid ${border}`,
                borderRadius: 2,
                display: "flex",
                flexDirection: "column",
                gap: 1.5,
              }}
            >
              <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
                <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                  Role details
                </Typography>
                <Box display="flex" gap={1}>
                  <Button
                    size="small"
                    variant="contained"
                    startIcon={<SaveOutlinedIcon />}
                    onClick={handleSaveMeta}
                    disabled={savingMeta || isSystemRole}
                    sx={{ textTransform: "none", fontWeight: 700 }}
                  >
                    {savingMeta ? "Saving..." : "Save details"}
                  </Button>
                  <Tooltip title={isSystemRole ? "System role cannot be deleted" : "Delete role"}>
                    <span>
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => setConfirmDelete(true)}
                        disabled={isSystemRole || deletingId === selectedRole.id}
                        sx={{ border: `1px solid ${border}` }}
                      >
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                </Box>
              </Box>
              <Box display="flex" gap={1.5} flexWrap="wrap" alignItems="center">
                <TextField
                  size="small"
                  label="Name"
                  value={nameDraft}
                  onChange={(e) => setNameDraft(e.target.value)}
                  disabled={isSystemRole}
                  sx={{ minWidth: 220, flex: 1 }}
                />
                <Box display="flex" alignItems="center" gap={0.5}>
                  <Typography variant="caption" sx={{ fontWeight: 700, mr: 0.5 }}>
                    Color:
                  </Typography>
                  {ROLE_COLORS.map((c) => (
                    <Box
                      key={c}
                      onClick={() => !isSystemRole && setColorDraft(c)}
                      sx={{
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        bgcolor: c,
                        cursor: isSystemRole ? "not-allowed" : "pointer",
                        border:
                          colorDraft === c
                            ? `3px solid ${alpha(c, 0.6)}`
                            : `1px solid ${border}`,
                      }}
                    />
                  ))}
                </Box>
                <Box display="flex" alignItems="center" gap={0.5}>
                  <Checkbox
                    size="small"
                    checked={isDefaultDraft}
                    onChange={(e) => setIsDefaultDraft(e.target.checked)}
                    disabled={isSystemRole}
                  />
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>
                    Default for new users
                  </Typography>
                </Box>
              </Box>
            </Box>

            {/* Page access */}
            <Box
              sx={{
                p: 2,
                border: `1px solid ${border}`,
                borderRadius: 2,
                display: "flex",
                flexDirection: "column",
                gap: 1,
              }}
            >
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                  Page access
                </Typography>
                <Button
                  size="small"
                  variant="contained"
                  startIcon={<SaveOutlinedIcon />}
                  onClick={handleSavePerms}
                  disabled={savingPerms || isSystemRole}
                  sx={{ textTransform: "none", fontWeight: 700 }}
                >
                  {savingPerms ? "Saving..." : "Save permissions"}
                </Button>
              </Box>
              <Box
                display="grid"
                gap={0.5}
                sx={{
                  gridTemplateColumns: {
                    xs: "1fr",
                    sm: "1fr 1fr",
                    md: "1fr 1fr 1fr",
                  },
                }}
              >
                {PAGE_ACTIONS.map((a) => (
                  <Box key={a.value} display="flex" alignItems="center" gap={0.5}>
                    <Checkbox
                      size="small"
                      checked={hasGlobalPerm(a.value)}
                      onChange={(e) => togglePerm(a.value, e.target.checked)}
                      disabled={isSystemRole}
                    />
                    <Typography variant="body2">{a.label}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Admin permissions */}
            <Box
              sx={{
                p: 2,
                border: `1px solid ${border}`,
                borderRadius: 2,
                display: "flex",
                flexDirection: "column",
                gap: 1,
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                Admin permissions
              </Typography>
              {ADMIN_ACTIONS.map((a) => (
                <Box key={a.value} display="flex" alignItems="center" gap={0.75}>
                  <Checkbox
                    size="small"
                    checked={hasGlobalPerm(a.value)}
                    onChange={(e) => togglePerm(a.value, e.target.checked)}
                    disabled={isSystemRole}
                  />
                  <Box sx={{ minWidth: 0 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {a.label}
                    </Typography>
                    {a.description && (
                      <Typography variant="caption" color="text.secondary">
                        {a.description}
                      </Typography>
                    )}
                  </Box>
                </Box>
              ))}
            </Box>

            {/* Data permissions (scoped) */}
            <Box
              sx={{
                p: 2,
                border: `1px solid ${border}`,
                borderRadius: 2,
                display: "flex",
                flexDirection: "column",
                gap: 1.5,
              }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 800 }}>
                Data permissions
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Tick "All" to grant globally, or add scoped rows for specific projects / channels.
              </Typography>
              {DATA_ACTIONS.map((a) => {
                const rows = scopedRows(a.value);
                return (
                  <Box
                    key={a.value}
                    sx={{
                      p: 1,
                      borderRadius: 1.5,
                      border: `1px dashed ${border}`,
                      display: "flex",
                      flexDirection: "column",
                      gap: 0.75,
                    }}
                  >
                    <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
                      <Box display="flex" alignItems="center" gap={0.75}>
                        <Checkbox
                          size="small"
                          checked={hasGlobalPerm(a.value)}
                          onChange={(e) => togglePerm(a.value, e.target.checked)}
                          disabled={isSystemRole}
                        />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>
                            {a.label}
                          </Typography>
                          {a.description && (
                            <Typography variant="caption" color="text.secondary">
                              {a.description}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                      <Button
                        size="small"
                        startIcon={<AddIcon fontSize="small" />}
                        onClick={() => addScopedRow(a.value)}
                        disabled={isSystemRole}
                        sx={{ textTransform: "none" }}
                      >
                        Add scope
                      </Button>
                    </Box>
                    {rows.length > 0 && (
                      <Box display="flex" flexDirection="column" gap={0.5}>
                        {rows.map((row) => (
                          <Box
                            key={row.idx}
                            display="flex"
                            gap={0.75}
                            alignItems="center"
                          >
                            <Select
                              size="small"
                              value={row.scope_type}
                              onChange={(e) =>
                                updateScopedRow(row.idx, "scope_type", e.target.value)
                              }
                              disabled={isSystemRole}
                              sx={{ width: 130 }}
                            >
                              {SCOPE_TYPES.filter((s) => s.value !== "*").map(
                                (s) => (
                                  <MenuItem key={s.value} value={s.value}>
                                    {s.label}
                                  </MenuItem>
                                )
                              )}
                            </Select>
                            <TextField
                              size="small"
                              placeholder="name / account_tag"
                              value={row.scope_value}
                              onChange={(e) =>
                                updateScopedRow(row.idx, "scope_value", e.target.value)
                              }
                              disabled={isSystemRole}
                              sx={{ flex: 1 }}
                            />
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => removeScopedRow(row.idx)}
                              disabled={isSystemRole}
                            >
                              <DeleteOutlineIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        ))}
                      </Box>
                    )}
                  </Box>
                );
              })}
            </Box>
          </Box>
        )}
      </Box>

      <Dialog open={confirmDelete} onClose={() => setConfirmDelete(false)} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>Delete role?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Role <b>{selectedRole?.name}</b> will be removed and unassigned from all members.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(false)} sx={{ textTransform: "none" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDeleteRole}
            disabled={deletingId === selectedRole?.id}
            sx={{ textTransform: "none", fontWeight: 700 }}
          >
            {deletingId === selectedRole?.id ? "Deleting..." : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default RoleManagement;
