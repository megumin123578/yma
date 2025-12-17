import { createContext, useState, useEffect } from "react";

export const UserContext = createContext();

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState({
    name: "Admin",
    avatar: null,
  });
  useEffect(() => {
    const saved = localStorage.getItem("userProfile");
    if (saved) setUser(JSON.parse(saved));
  }, []);

  useEffect(() => {
    localStorage.setItem("userProfile", JSON.stringify(user));
  }, [user]);

  return (
    <UserContext.Provider value={{ user, setUser }}>
      {children}
    </UserContext.Provider>
  );
};