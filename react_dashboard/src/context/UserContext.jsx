import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getMe, getMyPermissions } from "../services/userService";

export const UserContext = createContext(null);

const STORAGE_KEY = "userProfile";

const loadStoredUser = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const EMPTY_PERMISSIONS = { permissions: [], roles: [], is_admin: false, is_owner: false };

export const UserProvider = ({ children }) => {
  const [user, setUserState] = useState(() => loadStoredUser());
  const [permissionData, setPermissionData] = useState(EMPTY_PERMISSIONS);
  const [loading, setLoading] = useState(true);

  const setUser = (value) => {
    setUserState((prev) => {
      const next = typeof value === "function" ? value(prev) : value;
      if (next) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } else {
        localStorage.removeItem(STORAGE_KEY);
        setPermissionData(EMPTY_PERMISSIONS);
      }
      return next;
    });
  };

  const refreshPermissions = async () => {
    try {
      const data = await getMyPermissions();
      setPermissionData({
        permissions: Array.isArray(data?.permissions) ? data.permissions : [],
        roles: Array.isArray(data?.roles) ? data.roles : [],
        is_admin: !!data?.is_admin,
        is_owner: !!data?.is_owner,
      });
    } catch {
      setPermissionData(EMPTY_PERMISSIONS);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      setUser(null);
      setPermissionData(EMPTY_PERMISSIONS);
      setLoading(false);
      return;
    }

    const storedUser = loadStoredUser();

    Promise.all([getMe(), getMyPermissions().catch(() => null)])
      .then(([userData, permData]) => {
        const merged = {
          ...userData,
          name: userData?.name || storedUser?.name || userData?.username || "",
          avatar:
            userData?.avatar !== undefined
              ? userData.avatar
              : storedUser?.avatar || null,
          smmstore_api_key:
            userData?.smmstore_api_key !== undefined
              ? userData.smmstore_api_key
              : storedUser?.smmstore_api_key || "",
        };
        setUser(merged);
        if (permData) {
          setPermissionData({
            permissions: Array.isArray(permData?.permissions) ? permData.permissions : [],
            roles: Array.isArray(permData?.roles) ? permData.roles : [],
            is_admin: !!permData?.is_admin,
          });
        }
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        setUser(null);
        setPermissionData(EMPTY_PERMISSIONS);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return undefined;
    let inFlight = false;
    const maybeRefresh = () => {
      if (document.visibilityState !== "visible") return;
      if (inFlight) return;
      if (!localStorage.getItem("access_token")) return;
      inFlight = true;
      refreshPermissions().finally(() => {
        inFlight = false;
      });
    };
    document.addEventListener("visibilitychange", maybeRefresh);
    window.addEventListener("focus", maybeRefresh);
    return () => {
      document.removeEventListener("visibilitychange", maybeRefresh);
      window.removeEventListener("focus", maybeRefresh);
    };
  }, []);

  const value = useMemo(
    () => ({
      user,
      setUser,
      loading,
      permissions: permissionData.permissions,
      roles: permissionData.roles,
      isAdmin: permissionData.is_admin || !!user?.is_admin,
      isOwner: permissionData.is_owner || !!user?.is_owner,
      refreshPermissions,
    }),
    [user, loading, permissionData]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
};

// ---------- Hooks ----------

const matchesScope = (perm, scopeType, scopeValue) => {
  if (perm.scope_type === "*") return true;
  if (!scopeType) return false;
  return perm.scope_type === scopeType && (perm.scope_value || "") === scopeValue;
};

export const useHasPermission = (action, scope) => {
  const ctx = useContext(UserContext);
  if (!ctx) return false;
  if (ctx.isAdmin) return true;
  const perms = ctx.permissions || [];
  const scopeType = scope?.type || scope?.scope_type;
  const scopeValue = scope?.value ?? scope?.scope_value ?? "";
  return perms.some(
    (p) => p.action === action && matchesScope(p, scopeType, scopeValue)
  );
};

export const useIsOwner = () => {
  const ctx = useContext(UserContext);
  return !!ctx?.isOwner;
};

export const useAllowedScopes = (action, scopeType = "project") => {
  const ctx = useContext(UserContext);
  if (!ctx) return new Set();
  if (ctx.isAdmin) return null; // null = unlimited
  const perms = ctx.permissions || [];
  const out = new Set();
  for (const p of perms) {
    if (p.action !== action) continue;
    if (p.scope_type === "*") return null;
    if (p.scope_type === scopeType && p.scope_value) out.add(p.scope_value);
  }
  return out;
};
