"use client"

import * as React from "react"

import {
  DropdownMenu,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import Image from "next/image";
import { useRouter } from "next/navigation";

export function TeamSwitcher({
  teams,
}: {
  teams: {
    name: string
    logo: React.ElementType
    plan: string,
    url: string
  }[]
}) {
  const [activeTeam] = React.useState(teams[0]);
  const router = useRouter();

  if (!activeTeam) {
    return null
  }

  const handleClick = () => {
    router.push(activeTeam.url)
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                onClick={handleClick}
              />
            }
          >
            <div className="text-sidebar-primary-foreground flex aspect-square size-8 items-center justify-center rounded-lg">
              <Image src="/icons/icon-48x48.png" alt="Buddhi AI Logo" width={32} height={32} />
            </div>
            <div className="grid flex-1 text-left text-sm leading-tight">
              <span className="truncate font-medium">{activeTeam.name}</span>
              <span className="truncate text-xs">{activeTeam.plan}</span>
            </div>
          </DropdownMenuTrigger>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}