"use client";

import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Table, TableHeader, TableHead, TableRow, TableBody, TableCell,
} from "@/components/ui/table";
import { readGroups, removeItem, removeGroup, RowData } from "@/lib/groups-storage";
import Link from "next/link";

import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useEffect, useState } from "react";
import { Settings } from "lucide-react";

export default function GroupPage() {
    
  const params = useParams<{ name: string }>();
  const router = useRouter();
  const groupName = decodeURIComponent(params.name);
  const [items, setItems] = useState<RowData[] | null>(null);

  useEffect(() => {
    const load = () => {
      const groups = readGroups();
      setItems(groups[groupName] ?? null);
    };
    load();

    const handler = () => load();
    window.addEventListener("groups:update", handler);
    return () => window.removeEventListener("groups:update", handler);
  }, [groupName]);

  if (items === null) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold">Group not found</h1>
        <Link href="/">Back</Link>
      </div>
    );
  }

  const handleDeleteGroup = () => {
    if (confirm(`Delete group "${groupName}"?`)) {
      removeGroup(groupName);
      router.push("/");
    }
  };
  

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          {groupName} <span className="text-sm text-muted-foreground">({items.length})</span>
        </h1>
        <div className="flex gap-2">
          <Button variant="destructive" onClick={handleDeleteGroup}>
            Delete group
          </Button>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No items in this group.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[160px]">ID</TableHead>
              <TableHead>Notice</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((row) => (
              <TableRow key={String(row.id)}>
                <TableCell>{String(row.id)}</TableCell>
                <TableCell>{row.notice_id ?? "-"}</TableCell>
                <TableCell>
                  
                  <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" aria-label="Open menu" size="icon-sm">
            <Settings />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-40" align="end">
          <DropdownMenuLabel>File Actions</DropdownMenuLabel>
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => removeItem(groupName, row.id)}>
              Remove item
            </DropdownMenuItem>
            <DropdownMenuItem >
              Share...
            </DropdownMenuItem>
            <DropdownMenuItem disabled>Download</DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
