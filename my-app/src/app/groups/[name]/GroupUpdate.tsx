// components/GroupNameSheet.tsx
"use client";

import { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter, SheetTrigger } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";


type Props = {
  trigger: React.ReactNode;
  initialName?: string;
  onSubmit: (nextName: string) => Promise<void> | void;
  mode?: "create" | "rename";
};

export default function GroupNameSheet({ trigger, initialName = "", onSubmit, mode = "create" }: Props) {
  const [name, setName] = useState(initialName);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const label = mode === "rename" ? "Update" : "Save";

  const handle = async () => {
    setLoading(true);
    await onSubmit(name);
    setLoading(false);
    setOpen(false);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>{trigger}</SheetTrigger>
      <SheetContent className="p-3">
        <SheetHeader>
          <SheetTitle>{mode === "rename" ? "Rename Group" : "Add to Group"}</SheetTitle>
          <SheetDescription>
            {mode === "rename" ? "Choose a new name for this group." : "Create a new group or select an existing one."}
          </SheetDescription>

                <div className="mt-5  grid gap-2">
             <Label htmlFor="group-name" className="text-base">Group name</Label>
          <Input
            id="group-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handle()}
            autoFocus
            placeholder="e.g. Favorites"
          />
        </div>

        </SheetHeader>

        
         
        

        <SheetFooter>
          <Button onClick={handle} disabled={!name.trim() || loading}>
            {label}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
