import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuthStore = create(
  persist(
    (set) => ({
      credentials: null,
      isAuthenticated: false,

      setCredentials: (username, password) => {
        const credentials = btoa(`${username}:${password}`);
        set({ credentials, isAuthenticated: true });
      },

      clearCredentials: () => {
        set({ credentials: null, isAuthenticated: false });
      },

      getAuthHeader: () => {
        const state = useAuthStore.getState();
        if (!state.credentials) return null;
        return `Basic ${state.credentials}`;
      },
    }),
    {
      name: "troi-auth-storage",
    }
  )
);
