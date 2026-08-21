import { Badge } from "@/components/ui/badge";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  ok: "default",
  error: "destructive",
};

const STATUS_LABEL: Record<string, string> = {
  ok: "OK",
  error: "Error",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{STATUS_LABEL[status] ?? status}</Badge>
  );
}
