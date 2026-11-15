import { ProjectWorkspace } from "@/components/build/project-workspace";

export default async function BuildProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ProjectWorkspace projectId={projectId} />;
}
