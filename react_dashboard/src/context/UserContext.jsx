import { createContext, useState, useEffect } from "react";

export const UserContext = createContext(null);

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  // ✅ CHỈ LOAD USER TỪ BACKEND (LOGIN)
  useEffect(() => {
    const saved = localStorage.getItem("userProfile");
    if (!saved) return;

    try {
      const parsed = JSON.parse(saved);

      // 🚫 CHẶN avatar preview / base64
      if (
        parsed.avatar &&
        (parsed.avatar.startsWith("blob:") ||
          parsed.avatar.startsWith("data:image"))
      ) {
        parsed.avatar = null;
      }

      setUser(parsed);
    } catch {
      setUser(null);
    }
  }, []);

  // ✅ CHỈ LƯU USER KHI DỮ LIỆU LÀ TỪ BACKEND
  useEffect(() => {
    if (!user) {
      localStorage.removeItem("userProfile");
      return;
    }

    // 🚫 TUYỆT ĐỐI KHÔNG LƯU blob / base64
    if (
      user.avatar &&
      (user.avatar.startsWith("blob:") ||
        user.avatar.startsWith("data:image"))
    ) {
      return;
    }

    localStorage.setItem("userProfile", JSON.stringify(user));
  }, [user]);

  return (
    <UserContext.Provider value={{ user, setUser }}>
      {children}
    </UserContext.Provider>
  );
};
