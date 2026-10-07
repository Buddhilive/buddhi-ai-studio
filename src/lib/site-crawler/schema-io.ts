import { z } from "zod";
import { ExtractionSchema, FieldDefinition } from "./types";

const baseFieldSchema = z.object({
  name: z
    .string()
    .min(1)
    .max(64)
    .regex(/^[A-Za-z_][A-Za-z0-9_]{0,63}$/, "Must be valid identifier"),
  type: z.enum(["string", "number", "boolean", "string_list", "object"]),
  description: z.string().max(500).default(""),
  required: z.boolean().default(false),
});

export const fieldDefinitionSchema: z.ZodType<FieldDefinition> = baseFieldSchema.extend({
  fields: z.lazy(() => fieldDefinitionSchema.array().optional()),
});

export const extractionSchemaZod = z.object({
  mode: z.enum(["single", "many"]),
  fields: z.array(fieldDefinitionSchema).min(1).max(50),
  version: z.number().default(1),
});

export function parseSchemaFromJson(
  jsonStr: string
): { success: true; schema: ExtractionSchema } | { success: false; error: string } {
  try {
    const raw = JSON.parse(jsonStr);
    const parsed = extractionSchemaZod.safeParse(raw);
    if (!parsed.success) {
      return {
        success: false,
        error: parsed.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join(", "),
      };
    }
    return { success: true, schema: parsed.data as ExtractionSchema };
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return { success: false, error: `Invalid JSON format: ${msg}` };
  }
}

export function downloadSchemaAsJson(schema: ExtractionSchema, filename = "extraction-schema.json"): void {
  const jsonStr = JSON.stringify(schema, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
