// Mirror of python_backend/api/auth/permissions.py action vocabulary.
// Keep in sync if backend adds/removes verbs.

export const PAGE_GROUPS = [
  {
    label: "Dashboard",
    actions: [{ value: "page.dashboard", label: "Dashboard" }],
  },
  {
    label: "Analytics",
    actions: [
      { value: "page.all_channels", label: "All Channels" },
      { value: "page.content", label: "Content" },
      { value: "page.traffic", label: "Traffic Source" },
      { value: "page.geography", label: "Geography" },
      { value: "page.audience", label: "Audience" },
      { value: "page.reach", label: "Reach" },
      { value: "page.revenue", label: "Revenue" },
    ],
  },
  {
    label: "Statistics",
    actions: [
      { value: "page.channel_compare", label: "Channel Compare" },
      { value: "page.rivals", label: "Rivals" },
    ],
  },
  {
    label: "Automation",
    actions: [
      { value: "page.smmstore", label: "SMMStore" },
      { value: "page.mail", label: "Email Manager" },
    ],
  },
  {
    label: "Setting",
    actions: [{ value: "page.config", label: "Settings" }],
  },
];

export const PAGE_ACTIONS = PAGE_GROUPS.flatMap((g) => g.actions);

export const ADMIN_ACTIONS = [
  { value: "manage_users", label: "Manage users", description: "Add/remove users, reset password" },
  { value: "manage_roles", label: "Manage roles", description: "Create roles, assign permissions" },
  { value: "manage_mail", label: "Manage mail", description: "Add/sync/delete Gmail accounts" },
  { value: "manage_structure", label: "Manage structure", description: "Projects, channels, schedules" },
  { value: "view_all_channels", label: "View all channels", description: "Bypass project-based visibility; see every channel" },
];

export const SCOPE_TYPES = [
  { value: "*", label: "All (global)" },
  { value: "project", label: "Project" },
  { value: "channel", label: "Channel" },
];
