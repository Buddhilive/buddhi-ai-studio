"use client"

import { usePathname } from "next/navigation"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import React from "react"

const SEGMENT_LABELS: Record<string, string> = {
  chat: "Playground",
  models: "Models",
  settings: "Settings",
  documentation: "Documentation",
}

function toLabel(segment: string): string {
  return (
    SEGMENT_LABELS[segment.toLowerCase()] ??
    segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ")
  )
}

export function DynamicBreadcrumb() {
  const pathname = usePathname()

  const segments = pathname
    .split("/")
    .filter(Boolean)

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem className="hidden md:block">
          <BreadcrumbLink href="/">Buddhi AI Studio</BreadcrumbLink>
        </BreadcrumbItem>

        {segments.length === 0 ? (
          <>
            <BreadcrumbSeparator className="hidden md:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>Dashboard</BreadcrumbPage>
            </BreadcrumbItem>
          </>
        ) : (
          segments.map((segment, index) => {
            const isLast = index === segments.length - 1
            const href = "/" + segments.slice(0, index + 1).join("/")
            const label = toLabel(segment)

            return (
              <React.Fragment key={href}>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  {isLast ? (
                    <BreadcrumbPage>{label}</BreadcrumbPage>
                  ) : (
                    <BreadcrumbLink href={href}>{label}</BreadcrumbLink>
                  )}
                </BreadcrumbItem>
              </React.Fragment>
            )
          })
        )}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
