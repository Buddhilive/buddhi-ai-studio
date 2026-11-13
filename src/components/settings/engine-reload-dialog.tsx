"use client";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AlertTriangleIcon, Loader2Icon } from "lucide-react";

interface EngineReloadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
  isSaving: boolean;
  previousTokens: number;
  newTokens: number;
}

export function EngineReloadDialog({
  open,
  onOpenChange,
  onConfirm,
  isSaving,
  previousTokens,
  newTokens,
}: EngineReloadDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-500">
            <AlertTriangleIcon className="size-5" aria-hidden="true" />
            <DialogTitle>Confirm Context Window Update</DialogTitle>
          </div>
          <DialogDescription className="pt-2 text-sm text-muted-foreground">
            Changing the context window from{" "}
            <span className="font-mono font-medium text-foreground">
              {previousTokens.toLocaleString()}
            </span>{" "}
            to{" "}
            <span className="font-mono font-medium text-foreground">
              {newTokens.toLocaleString()}
            </span>{" "}
            requires LiteRT to reallocate model KV-cache memory and reload the local engine.
            Active inference sessions will be reinitialized.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={() => void onConfirm()}
            disabled={isSaving}
          >
            {isSaving ? (
              <>
                <Loader2Icon className="size-4 animate-spin mr-1.5" aria-hidden="true" />
                Reloading Engine...
              </>
            ) : (
              "Confirm & Reload"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
