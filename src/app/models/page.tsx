import { ModelsView } from "@/components/models-view";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Models - Buddhi AI Studio",
  description: "Manage your AI models and downloads.",
};

export default function ModelsPage() {
  return <ModelsView />;
}
