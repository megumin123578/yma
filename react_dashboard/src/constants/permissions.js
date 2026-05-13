// Mirror of python_backend/api/auth/permissions.py action vocabulary.
// Keep in sync if backend adds/removes verbs.

export const PAGE_ACTIONS = [
  { value: "page.dashboard", label: "Dashboard" },
  { value: "page.content", label: "Content / Channels" },
  { value: "page.audience", label: "Audience" },
  { value: "page.revenue", label: "Revenue" },
  { value: "page.reach", label: "Reach" },
  { value: "page.traffic", label: "Traffic source" },
  { value: "page.geography", label: "Geography" },
  { value: "page.smmstore", label: "SMMStore" },
  { value: "page.mail", label: "Email Manager" },
  { value: "page.rivals", label: "Rivals" },
  { value: "page.config", label: "Settings" },
];

export const DATA_ACTIONS = [
  { value: "read", label: "Read", description: "View channel/project data" },
  { value: "write", label: "Write", description: "Edit configuration, rename, move" },
  { value: "run", label: "Run", description: "Trigger sync stages" },
  { value: "delete", label: "Delete", description: "Remove tokens or accounts" },
];

export const ADMIN_ACTIONS = [
  { value: "manage_users", label: "Manage users", description: "Add/remove users, reset password" },
  { value: "manage_roles", label: "Manage roles", description: "Create roles, assign permissions" },
  { value: "manage_mail", label: "Manage mail", description: "Add/sync/delete Gmail accounts" },
  { value: "manage_structure", label: "Manage structure", description: "Projects, channels, schedules" },
];

export const SCOPE_TYPES = [
  { value: "*", label: "All (global)" },
  { value: "project", label: "Project" },
  { value: "channel", label: "Channel" },
];
