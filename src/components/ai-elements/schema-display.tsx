"use client";

import * as React from "react";
import { DatabaseIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export interface SchemaColumn {
  name: string;
  type: string;
  nullable?: boolean;
  primaryKey?: boolean;
}

export interface SchemaTable {
  name: string;
  columns: SchemaColumn[];
}

export interface SchemaDisplayProps {
  dialect?: string;
  tables: SchemaTable[];
  className?: string;
}

export function SchemaDisplay({
  dialect = "postgresql",
  tables,
  className,
}: SchemaDisplayProps) {
  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card text-xs",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border bg-muted/40 px-3 py-2">
        <div className="flex items-center gap-2">
          <DatabaseIcon className="size-3.5 text-primary" aria-hidden="true" />
          <span className="font-semibold">Schema Display</span>
        </div>
        <Badge variant="outline" className="font-mono text-[10px]">
          {dialect}
        </Badge>
      </div>

      {tables.length === 0 ? (
        <div className="p-3 text-muted-foreground">No schema tables available.</div>
      ) : (
        <div className="space-y-3 p-3">
          {tables.map((table) => (
            <div key={table.name} className="overflow-hidden rounded border border-border/80">
              <div className="border-b border-border/60 bg-muted/30 px-2.5 py-1.5 font-mono text-[11px] font-semibold">
                {table.name}
              </div>
              <div className="overflow-x-auto" tabIndex={0}>
                <table className="w-full text-left font-mono text-[11px]">
                  <thead className="border-b border-border/60 bg-muted/20 text-muted-foreground">
                    <tr>
                      <th scope="col" className="px-2.5 py-1 font-medium">
                        Column
                      </th>
                      <th scope="col" className="px-2.5 py-1 font-medium">
                        Type
                      </th>
                      <th scope="col" className="px-2.5 py-1 font-medium">
                        Constraints
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/40">
                    {table.columns.map((col) => (
                      <tr key={col.name}>
                        <td className="px-2.5 py-1 font-medium text-foreground">
                          {col.name}
                        </td>
                        <td className="px-2.5 py-1 text-muted-foreground">{col.type}</td>
                        <td className="px-2.5 py-1 text-muted-foreground">
                          {col.primaryKey ? "PK " : ""}
                          {col.nullable === false ? "NOT NULL" : "NULL"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
