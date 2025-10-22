"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  SidebarGroup, SidebarGroupContent, SidebarMenu, SidebarMenuItem, SidebarMenuButton,
} from "@/components/ui/sidebar";
import { readGroups, GROUPS_KEY, GROUPS_UPDATE } from "@/lib/groups-storage";

export default function SidebarGroups() {
  const [groups, setGroups] = useState<Record<string, any[]>>({});

  useEffect(() => {
    const load = () => setGroups(readGroups());

    load(); // initial
    // same-tab updates
    const onUpdate = () => load();
    // cross-tab updates (fires in *other* tabs)
    const onStorage = (e: StorageEvent) => {
      if (e.key === GROUPS_KEY) load();
    };

    window.addEventListener(GROUPS_UPDATE, onUpdate);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(GROUPS_UPDATE, onUpdate);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  return (
    <SidebarGroup className="-mt-3">
      <SidebarGroupContent>
        <SidebarMenu>
          {Object.entries(groups).map(([groupName, items]) => (
            <SidebarMenuItem key={groupName}>
              <SidebarMenuButton asChild>
                <Link href={`/groups/${encodeURIComponent(groupName)}`}>
                  {groupName} ({items.length})
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
          {Object.keys(groups).length === 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">No groups yet</div>
          )}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  );
}
