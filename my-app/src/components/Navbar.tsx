"use client";

import { LogOut, Moon, Settings, Sun, User } from "lucide-react";
import Link from "next/link";

// UI
import { Avatar, AvatarFallback, AvatarImage } from "./ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "./ui/button";
import { useTheme } from "next-themes";
import { SidebarTrigger } from "./ui/sidebar";
import { ProfileAvatar } from "./ui/profile-avatar";

const Navbar = () => {
  const { theme, setTheme } = useTheme();

  return (
    <nav className="items-center flex justify-between p-4">
      <SidebarTrigger />
      <div className="flex items-center gap-4">
        
        {/* Light mode */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="icon">
              <Sun className="h-[1.2rem] w-[1.2rem] scale-100 rotate-0 transition-all dark:scale-0 dark:-rotate-90" />
              <Moon className="absolute h-[1.2rem] w-[1.2rem] scale-0 rotate-90 transition-all dark:scale-100 dark:rotate-0" />
              <span className="sr-only">Toggle theme</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setTheme("light")}>
              Šviesus
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("dark")}>
              Tamsus
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => setTheme("system")}>
              Systemos
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {/* Profile */}
        <DropdownMenu>
          <DropdownMenuTrigger>
            <ProfileAvatar/>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuLabel>Paskyra</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="h-[1.2rem] w-[1.2rem] mr-1" />
              Profilis
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Settings className="h-[1.2rem] w-[1.2rem] mr-1" />
                  Nustatymai
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive">
              <LogOut className="h-[1.2rem] w-[1.2rem] mr-1" />
                  Atsijungti
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  );
};

export default Navbar;
