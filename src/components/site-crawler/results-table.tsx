"use client";

import * as React from "react";
import { ExternalLinkIcon, SearchIcon, TableIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ExtractionSchema } from "@/lib/site-crawler/types";

export function ResultsTable({
  records,
  schema,
}: {
  records: Record<string, unknown>[];
  schema?: ExtractionSchema;
}) {
  const [filterQuery, setFilterQuery] = React.useState("");

  const fields = schema?.fields || [];
  const fieldNames = fields.length > 0
    ? fields.map((f) => f.name)
    : Object.keys(records[0] || {}).filter((k) => k !== "source_url" && k !== "extracted_at");

  const filteredRecords = React.useMemo(() => {
    if (!filterQuery.trim()) return records;
    const q = filterQuery.toLowerCase();
    return records.filter((r) =>
      Object.values(r).some((val) =>
        String(val ?? "").toLowerCase().includes(q)
      )
    );
  }, [records, filterQuery]);

  const renderCellContent = (val: unknown) => {
    if (val === null || val === undefined) {
      return <span className="text-muted-foreground/60 italic text-xs">null</span>;
    }
    if (typeof val === "boolean") {
      return (
        <Badge variant={val ? "secondary" : "outline"} className="text-[11px] py-0 px-1.5">
          {val ? "true" : "false"}
        </Badge>
      );
    }
    if (Array.isArray(val)) {
      return (
        <span className="text-xs font-mono text-muted-foreground">
          [{val.map((item) => String(item)).join(", ")}]
        </span>
      );
    }
    if (typeof val === "object") {
      return (
        <span className="text-xs font-mono text-muted-foreground">
          {JSON.stringify(val)}
        </span>
      );
    }
    return <span className="text-xs">{String(val)}</span>;
  };

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <TableIcon className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">Extracted Structured Records</CardTitle>
              <Badge variant="outline" className="text-xs font-mono">
                {records.length} {records.length === 1 ? "record" : "records"}
              </Badge>
            </div>
            <CardDescription>
              Structured dataset extracted by the local LLM conforming to your defined schema.
            </CardDescription>
          </div>

          <div className="relative w-full sm:w-64">
            <SearchIcon className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Filter records..."
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              className="pl-8 h-8 text-xs"
            />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {filteredRecords.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground text-xs">
            {records.length === 0 ? "No records extracted yet." : "No records match your filter."}
          </div>
        ) : (
          <div className="rounded-md border border-border/60 overflow-hidden">
            <div className="overflow-x-auto max-h-[460px]">
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0 z-10 backdrop-blur-sm">
                  <TableRow>
                    <TableHead className="w-12 text-xs">#</TableHead>
                    {fieldNames.map((name) => (
                      <TableHead key={name} className="text-xs font-semibold capitalize font-mono">
                        {name}
                      </TableHead>
                    ))}
                    <TableHead className="text-xs font-semibold">Source URL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRecords.map((rec, i) => (
                    <TableRow key={i} className="hover:bg-muted/30">
                      <TableCell className="text-xs text-muted-foreground font-mono">
                        {i + 1}
                      </TableCell>
                      {fieldNames.map((name) => (
                        <TableCell key={name} className="max-w-xs truncate py-2.5">
                          {renderCellContent(rec[name])}
                        </TableCell>
                      ))}
                      <TableCell className="py-2.5 max-w-[200px] truncate">
                        {typeof rec.source_url === "string" ? (
                          <a
                            href={rec.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <span className="truncate">{rec.source_url}</span>
                            <ExternalLinkIcon className="h-3 w-3 shrink-0" />
                          </a>
                        ) : (
                          <span className="text-muted-foreground text-xs">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
