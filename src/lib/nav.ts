import { navData } from "@/components/app-sidebar"

const navLabels: Record<string, string> = Object.fromEntries(
  navData.navMain.flatMap((item) => {
    const entries: [string, string][] = []
    if (item.url !== "#") entries.push([item.url, item.title])
    for (const sub of item.items ?? []) {
      if (sub.url !== "#") entries.push([sub.url, sub.title])
    }
    return entries
  })
)

export function getBreadcrumbLabel(pathname: string): string {
  return navLabels[pathname] ?? "Untitled"
}
