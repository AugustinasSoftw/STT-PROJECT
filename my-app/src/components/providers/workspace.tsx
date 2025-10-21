"use client";

import { createContext, useContext, useMemo } from "react";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import type { SavedGroup, SavedPage } from "@/app/types/types";

type WorkspaceState = {
  groups: SavedGroup[];
  pages: SavedPage[];
  createGroup: (name: string) => string; // returns new groupId
  savePage: (page: Omit<SavedPage, "createdAt">) => void;
  removePage: (id: string) => void;
  renameGroup: (groupId: string, name: string) => void;
  toggleGroup: (groupId: string) => void;
};

const WorkspaceCtx = createContext<WorkspaceState | null>(null);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [groups, setGroups] = useLocalStorage<SavedGroup[]>("ws_groups", [
    { id: "default", name: "Ungrouped", isOpen: true },
  ]);
  const [pages, setPages] = useLocalStorage<SavedPage[]>("ws_pages", []);

  const api = useMemo<WorkspaceState>(
    () => ({
      groups,
      pages,

      createGroup: (name) => {
        const id = crypto.randomUUID();
        setGroups([...groups, { id, name, isOpen: true }]);
        return id;
      },

      savePage: (page) => {
        // avoid duplicates by id
        if (pages.some((p) => p.id === page.id)) return;
        setPages([...pages, { ...page, createdAt: new Date().toISOString() }]);
        // ensure group exists
        if (!groups.some((g) => g.id === page.groupId)) {
          setGroups([
            ...groups,
            { id: page.groupId, name: "New Group", isOpen: true },
          ]);
        }
      },

      removePage: (id) => {
        setPages(pages.filter((p) => p.id !== id));
      },

      renameGroup: (groupId, name) => {
        setGroups(groups.map((g) => (g.id === groupId ? { ...g, name } : g)));
      },

      toggleGroup: (groupId) => {
        setGroups(
          groups.map((g) =>
            g.id === groupId ? { ...g, isOpen: !g.isOpen } : g
          )
        );
      },
    }),
    [groups, pages, setGroups, setPages]
  );

  return <WorkspaceCtx.Provider value={api}>{children}</WorkspaceCtx.Provider>;
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceCtx);
  if (!ctx)
    throw new Error("useWorkspace must be used inside WorkspaceProvider");
  return ctx;
}
