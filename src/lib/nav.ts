import { navData } from "@/components/app-sidebar"

const allNavItems = [...navData.navMain, ...(navData.toolsAndApps ?? [])]

const navLabels: Record<string, string> = Object.fromEntries(
  allNavItems.flatMap((item) => {
    const entries: [string, string][] = []
    if (item.url !== "#") entries.push([item.url, item.title])
    for (const sub of item.items ?? []) {
      if (sub.url !== "#") entries.push([sub.url, sub.title])
    }
    return entries
  })
)

export function getBreadcrumbLabel(pathname: string): string {
  if (navLabels[pathname]) return navLabels[pathname]
  const match = Object.keys(navLabels)
    .filter((route) => route !== "/" && pathname.startsWith(route))
    .sort((a, b) => b.length - a.length)[0]
  if (match) return navLabels[match]
  return "Untitled"
}
