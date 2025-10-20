"use client";

import Link from "next/link";
import { useWorkspace } from "@/components/providers/workspace";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"; // your shadcn exports

export default function SavedSection() {
  const { groups, pages, toggleGroup, renameGroup } = useWorkspace();

  return (
    

      <>
        {groups.map(group => {
          const groupPages = pages.filter(p => p.groupId === group.id);

          return (
            <div key={group.id} className="mb-2">
              <div className="flex items-center justify-between px-2 py-1 text-[13px] text-zinc-300">
                <button
                  onClick={() => toggleGroup(group.id)}
                  className="hover:text-white"
                >
                  {group.isOpen ? "▾" : "▸"} {group.name}
                </button>
                <button
                  onClick={() => {
                    const name = window.prompt("Rename group", group.name);
                    if (name) renameGroup(group.id, name);
                  }}
                  className="text-zinc-500 hover:text-zinc-300"
                  title="Rename"
                >
                  ✎
                </button>
              </div>

              {group.isOpen && (
                <SidebarMenu>
                  {groupPages.length === 0 && (
                    <div className="px-3 py-1 text-xs text-zinc-500">
                      No saved pages
                    </div>
                  )}

                  {groupPages.map(p => (
                    <SidebarMenuItem key={p.id}>
                      <SidebarMenuButton asChild>
                        <Link href={p.href}>
                          <span className="truncate">{p.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              )}
            </div>
          );
        })}
    </>  
  );
}
