"use client";

import * as React from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileCode2Icon,
  FolderIcon,
  FolderOpenIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "directory";
  children?: FileTreeNode[];
}

export interface FileTreeProps {
  nodes: FileTreeNode[];
  selectedPath?: string | null;
  onSelectFile?: (path: string) => void;
  className?: string;
}

interface FlatItem {
  node: FileTreeNode;
  depth: number;
  isExpanded: boolean;
}

export function FileTree({
  nodes,
  selectedPath,
  onSelectFile,
  className,
}: FileTreeProps) {
  const [expanded, setExpanded] = React.useState<Record<string, boolean>>({});
  const [focusedPath, setFocusedPath] = React.useState<string | null>(null);
  const itemRefs = React.useRef<Record<string, HTMLDivElement | null>>({});

  const toggleDir = React.useCallback((path: string) => {
    setExpanded((prev) => ({ ...prev, [path]: !prev[path] }));
  }, []);

  const flatItems = React.useMemo(() => {
    const out: FlatItem[] = [];
    const walk = (list: FileTreeNode[], depth: number) => {
      for (const node of list) {
        const isExpanded = Boolean(expanded[node.path]);
        out.push({ node, depth, isExpanded });
        if (node.type === "directory" && isExpanded && node.children?.length) {
          walk(node.children, depth + 1);
        }
      }
    };
    walk(nodes, 0);
    return out;
  }, [nodes, expanded]);

  const activeFocusPath = focusedPath ?? selectedPath ?? flatItems[0]?.node.path ?? null;

  const focusItemAt = (index: number) => {
    const target = flatItems[index];
    if (!target) return;
    setFocusedPath(target.node.path);
    itemRefs.current[target.node.path]?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent, idx: number, item: FlatItem) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (idx + 1 < flatItems.length) focusItemAt(idx + 1);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (idx - 1 >= 0) focusItemAt(idx - 1);
        break;
      case "ArrowRight":
        e.preventDefault();
        if (item.node.type === "directory" && !item.isExpanded) {
          toggleDir(item.node.path);
        } else if (item.node.type === "directory" && item.isExpanded && idx + 1 < flatItems.length) {
          focusItemAt(idx + 1);
        }
        break;
      case "ArrowLeft":
        e.preventDefault();
        if (item.node.type === "directory" && item.isExpanded) {
          toggleDir(item.node.path);
        } else {
          const parentPath = item.node.path.split("/").slice(0, -1).join("/");
          const parentIdx = flatItems.findIndex((f) => f.node.path === parentPath);
          if (parentIdx >= 0) focusItemAt(parentIdx);
        }
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        if (item.node.type === "directory") {
          toggleDir(item.node.path);
        } else {
          onSelectFile?.(item.node.path);
        }
        break;
      default:
        break;
    }
  };

  if (nodes.length === 0) {
    return (
      <div className={cn("p-3 text-xs text-muted-foreground", className)}>
        No files in workspace.
      </div>
    );
  }

  return (
    <div
      role="tree"
      aria-label="Workspace files"
      className={cn("select-none py-1 text-xs", className)}
    >
      {flatItems.map((item, idx) => {
        const isDir = item.node.type === "directory";
        const isSelected = selectedPath === item.node.path;
        const isFocusable = activeFocusPath === item.node.path;

        return (
          <div
            key={item.node.path}
            ref={(el) => {
              itemRefs.current[item.node.path] = el;
            }}
            role="treeitem"
            aria-level={item.depth + 1}
            aria-expanded={isDir ? item.isExpanded : undefined}
            aria-selected={isSelected}
            tabIndex={isFocusable ? 0 : -1}
            onClick={() => {
              setFocusedPath(item.node.path);
              if (isDir) {
                toggleDir(item.node.path);
              } else {
                onSelectFile?.(item.node.path);
              }
            }}
            onKeyDown={(e) => handleKeyDown(e, idx, item)}
            style={{ paddingLeft: `${item.depth * 14 + 8}px` }}
            className={cn(
              "flex cursor-pointer items-center gap-1.5 rounded-sm py-1 pr-2 font-mono text-[12px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isSelected
                ? "bg-primary/15 font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            )}
          >
            {isDir ? (
              <>
                {item.isExpanded ? (
                  <ChevronDownIcon className="size-3.5 shrink-0" aria-hidden="true" />
                ) : (
                  <ChevronRightIcon className="size-3.5 shrink-0" aria-hidden="true" />
                )}
                {item.isExpanded ? (
                  <FolderOpenIcon className="size-3.5 shrink-0 text-amber-500" aria-hidden="true" />
                ) : (
                  <FolderIcon className="size-3.5 shrink-0 text-amber-500" aria-hidden="true" />
                )}
              </>
            ) : (
              <>
                <span className="w-3.5 shrink-0" aria-hidden="true" />
                <FileCode2Icon className="size-3.5 shrink-0 text-sky-500" aria-hidden="true" />
              </>
            )}
            <span className="truncate">{item.node.name}</span>
          </div>
        );
      })}
    </div>
  );
}
