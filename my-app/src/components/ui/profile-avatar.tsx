"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

export function ProfileAvatar() {
  const { resolvedTheme } = useTheme(); // "light" | "dark"
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => setMounted(true), []);

  // Avoid SSR mismatch: show fallback until mounted
  if (!mounted) {
    return (
      <Avatar>
        <AvatarFallback>U</AvatarFallback>
      </Avatar>
    );
  }

  const src = resolvedTheme === "dark" ? "/darkmode.png" : "/lightmode.png";

  return (
    <Avatar className="h-8 w-8">
      <AvatarImage src={src} alt="Profile" className="transition-opacity duration-300" />
      <AvatarFallback>U</AvatarFallback>
    </Avatar>
  );
}
