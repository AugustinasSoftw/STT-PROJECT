"use client";

import * as React from "react";
import {
  Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  SheetFooter, SheetClose
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const GROUPS_KEY = "groups:v1";
const GROUPS_UPDATE = "groups:update"; // <- notify same-tab readers

// Adjust this to your row shape
export type RowData = {
  id: string | number; // used to de-dupe
  [k: string]: any;
};

type Groups = Record<string, RowData[]>;

type SaveButtonProps = {
  rowValue: RowData;
};

function loadGroups(): Groups {
  try {
    const raw = localStorage.getItem(GROUPS_KEY);
    return raw ? (JSON.parse(raw) as Groups) : {};
  } catch {
    return {};
  }
}

function persistGroups(groups: Groups) {
  localStorage.setItem(GROUPS_KEY, JSON.stringify(groups));
  // IMPORTANT: tell the app to refresh any readers (sidebar, pages, etc.)
  window.dispatchEvent(new Event(GROUPS_UPDATE));
}

function addRowToGroup(groups: Groups, groupName: string, row: RowData): Groups {
  const name = groupName.trim();
  if (!name) return groups;

  const current = groups[name] ?? [];
  const exists = current.some((r) => r.id === row.id);
  const updated = exists ? current : [...current, row];

  return { ...groups, [name]: updated };
}

export function SaveButton({ rowValue }: SaveButtonProps) {
  const [groups, setGroups] = React.useState<Groups>({});
  const [newGroupName, setNewGroupName] = React.useState("");
  const [selectedGroup, setSelectedGroup] = React.useState<string>("");

  // Load groups on mount (client only)
  React.useEffect(() => {
    setGroups(loadGroups());
  }, []);

  const handleSave = (groupName: string) => {
    const incomingName = (groupName || newGroupName).trim();
    if (!incomingName) return;

    const next = addRowToGroup(groups, incomingName, rowValue);
    // Only write if there was a change
    if (next !== groups) {
      setGroups(next);
      persistGroups(next); // <- triggers "groups:update"
    }
    setNewGroupName("");
    setSelectedGroup(incomingName);
  };

  const existingNames = React.useMemo(() => Object.keys(groups).sort(), [groups]);

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Save</Button>
      </SheetTrigger>

      <SheetContent className="p-2">
        <SheetHeader>
          <SheetTitle>Add to Group</SheetTitle>
          <SheetDescription>
            Choose an existing group or create a new one, then click Save.
          </SheetDescription>

          <div className="mt-4 space-y-6">
            {/* New group input */}
            <div className="grid gap-2">
              <Label htmlFor="group-name">New group</Label>
              <Input
                id="group-name"
                placeholder="e.g. Favorites"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
              />
            </div>

            {/* Existing groups */}
            <div className="grid gap-3">
              <h2 className="text-sm font-medium">Or select an existing group:</h2>
              <div className="flex flex-col gap-2">
                {existingNames.length === 0 && (
                  <span className="text-muted-foreground text-sm">No groups yet.</span>
                )}
                {existingNames.map((name) => (
                  <button
                    key={name}
                    onClick={() => handleSave(name)}
                    className={`text-left rounded-lg border px-3 py-2 hover:bg-accent transition ${
                      selectedGroup === name ? "ring-2 ring-offset-2" : ""
                    }`}
                    title={`${groups[name].length} item(s)`}
                  >
                    <span className="block font-medium">{name}</span>
                    <span className="text-xs text-muted-foreground">
                      {groups[name].length} item(s)
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </SheetHeader>

        <SheetFooter className="mt-6">
          <Button
            onClick={() => handleSave(newGroupName)}
            className="justify-self-start"
            disabled={!newGroupName.trim()}
          >
            Save to new group
          </Button>
          <SheetClose asChild>
            <Button variant="outline">Close</Button>
          </SheetClose>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
