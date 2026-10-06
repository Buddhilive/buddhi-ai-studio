"use client";

import * as React from "react";
import {
  CodeIcon,
  DownloadIcon,
  PlusIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ExtractionMode, ExtractionSchema, FieldDefinition, FieldType } from "@/lib/site-crawler/types";
import { downloadSchemaAsJson, parseSchemaFromJson } from "@/lib/site-crawler/schema-io";

export function SchemaBuilder({
  schema,
  onChange,
  disabled = false,
}: {
  schema: ExtractionSchema;
  onChange: (updated: ExtractionSchema) => void;
  disabled?: boolean;
}) {
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);

  const handleModeChange = (mode: ExtractionMode) => {
    onChange({ ...schema, mode });
  };

  const handleAddField = () => {
    const newField: FieldDefinition = {
      name: `field_${schema.fields.length + 1}`,
      type: "string",
      description: "",
      required: false,
    };
    onChange({ ...schema, fields: [...schema.fields, newField] });
  };

  const handleRemoveField = (index: number) => {
    const updated = schema.fields.filter((_, i) => i !== index);
    onChange({ ...schema, fields: updated.length ? updated : [{ name: "title", type: "string", description: "", required: true }] });
  };

  const handleFieldChange = (index: number, partial: Partial<FieldDefinition>) => {
    const updated = [...schema.fields];
    updated[index] = { ...updated[index], ...partial };
    onChange({ ...schema, fields: updated });
  };

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      const res = parseSchemaFromJson(content);
      if (res.success) {
        onChange(res.schema);
      } else {
        alert(res.error);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <Card className="border-border/60">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <CodeIcon className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">3. Extraction Data Structure</CardTitle>
            </div>
            <CardDescription>
              Define the data attributes and types the local LLM will extract from each page.
            </CardDescription>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              accept=".json,application/json"
              className="hidden"
              onChange={handleImportFile}
            />
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
            >
              <UploadIcon className="h-3.5 w-3.5" />
              Import
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={() => downloadSchemaAsJson(schema)}
              disabled={disabled}
            >
              <DownloadIcon className="h-3.5 w-3.5" />
              Export
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Mode Selector */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 rounded-lg border border-border/50 bg-muted/30">
          <div>
            <Label className="text-xs font-semibold">Extraction Mode</Label>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              {schema.mode === "single"
                ? "Extract exactly one structured record per webpage (e.g. article, detail page)."
                : "Extract multiple records per webpage (e.g. product catalog, search results listing)."}
            </p>
          </div>
          <div className="flex items-center rounded-lg border border-border bg-background p-1">
            <Button
              variant={schema.mode === "single" ? "secondary" : "ghost"}
              size="xs"
              className="text-xs px-3 h-7 font-medium"
              onClick={() => handleModeChange("single")}
              disabled={disabled}
            >
              Single Record
            </Button>
            <Button
              variant={schema.mode === "many" ? "secondary" : "ghost"}
              size="xs"
              className="text-xs px-3 h-7 font-medium"
              onClick={() => handleModeChange("many")}
              disabled={disabled}
            >
              Many Records
            </Button>
          </div>
        </div>

        {/* Fields Table / Rows */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-medium">Fields to Extract ({schema.fields.length})</Label>
            <Button
              variant="outline"
              size="xs"
              className="h-7 gap-1 text-xs"
              onClick={handleAddField}
              disabled={disabled}
            >
              <PlusIcon className="h-3.5 w-3.5" />
              Add Field
            </Button>
          </div>

          <div className="space-y-2.5">
            {schema.fields.map((field, idx) => (
              <div
                key={idx}
                className="flex flex-col sm:flex-row sm:items-center gap-2.5 p-3 rounded-lg border border-border/60 bg-card"
              >
                {/* Field Name */}
                <div className="sm:w-1/4 space-y-1">
                  <Input
                    placeholder="attribute_name"
                    value={field.name}
                    onChange={(e) => handleFieldChange(idx, { name: e.target.value })}
                    className="h-8 font-mono text-xs"
                    disabled={disabled}
                  />
                </div>

                {/* Field Type */}
                <div className="sm:w-1/4">
                  <Select
                    value={field.type}
                    onValueChange={(val) => {
                      if (val) handleFieldChange(idx, { type: val as FieldType });
                    }}
                    disabled={disabled}
                  >
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue placeholder="Type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">Text (string)</SelectItem>
                      <SelectItem value="number">Number (float/int)</SelectItem>
                      <SelectItem value="boolean">Boolean (true/false)</SelectItem>
                      <SelectItem value="string_list">List of Strings</SelectItem>
                      <SelectItem value="object">Nested Object</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {/* Field Description */}
                <div className="flex-1">
                  <Input
                    placeholder="Extraction guidance (e.g. price in USD, main header)"
                    value={field.description}
                    onChange={(e) => handleFieldChange(idx, { description: e.target.value })}
                    className="h-8 text-xs"
                    disabled={disabled}
                  />
                </div>

                {/* Required switch & Delete */}
                <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <Switch
                      id={`req-${idx}`}
                      checked={field.required}
                      onCheckedChange={(checked) => handleFieldChange(idx, { required: checked })}
                      disabled={disabled}
                    />
                    <Label htmlFor={`req-${idx}`} className="text-[11px] text-muted-foreground cursor-pointer">
                      Req
                    </Label>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                    onClick={() => handleRemoveField(idx)}
                    disabled={disabled || schema.fields.length <= 1}
                  >
                    <Trash2Icon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
