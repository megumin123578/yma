import { createContext, useEffect, useState } from "react";
import { getMe } from "../services/userService";

export const UserContext = createContext(null);

// Persist user to localStorage so display name/avatar survive reloads until logout
const STORAGE_KEY = "userProfile";

const loadStoredUser = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const UserProvider = ({ children }) => {
  const [user, setUserState] = useState(() => loadStoredUser());
  const [loading, setLoading] = useState(true);

  const setUser = (value) => {
    setUserState((prev) => {
      const next = typeof value === "function" ? value(prev) : value;
      if (next) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
      return next;
    });
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    const storedUser = loadStoredUser();

    getMe()
      .then((userData) => {
        // Keep locally edited fields (e.g., display name) if backend doesn't provide them
        const merged = {
          ...userData,
          name: userData?.name || storedUser?.name || userData?.username || "",
          avatar:
            userData?.avatar !== undefined
              ? userData.avatar
              : storedUser?.avatar || null,
        };
        setUser(merged);
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        setUser(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <UserContext.Provider value={{ user, setUser, loading }}>
      {children}
    </UserContext.Provider>
  );
};
