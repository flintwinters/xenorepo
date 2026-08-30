/** OpenAPI-derived cockpit HTTP boundary. */
import createClient from "openapi-fetch";
import type { components, paths } from "../data/openapi";

const api = createClient<paths>();
export type Overview = components["schemas"]["Overview"];
export type ModuleFact = components["schemas"]["ModuleFact"];
export type TreeNode = components["schemas"]["TreeNode"];
export type Architecture = components["schemas"]["Architecture"];
export type Snapshot = components["schemas"]["SnapshotView"];
export type RepositoryHistory = components["schemas"]["RepositoryHistory"];

function result<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { error?: string; detail?: unknown };
    throw new Error(body.error ?? (typeof body.detail === "string" ? body.detail : "Request failed"));
  }
  if (data === undefined) throw new Error("Request returned no data");
  return data;
}

export async function loadCockpit(): Promise<
  [Overview, ModuleFact[], TreeNode, Architecture, RepositoryHistory, Snapshot[]]
> {
  const [overview, modules, tree, architecture, repositoryHistory, snapshots] = await Promise.all([
    api.GET("/api/overview"), api.GET("/api/modules"), api.GET("/api/tree"),
    api.GET("/api/architecture"), api.GET("/api/repository-history"), api.GET("/api/history"),
  ]);
  return [result(overview.data, overview.error), result(modules.data, modules.error),
    result(tree.data, tree.error), result(architecture.data, architecture.error),
    result(repositoryHistory.data, repositoryHistory.error), result(snapshots.data, snapshots.error)];
}

export async function captureSnapshot(): Promise<boolean> {
  const { data, error } = await api.POST("/api/snapshots");
  return result(data, error).created;
}

export async function loadHistory(): Promise<Snapshot[]> {
  const { data, error } = await api.GET("/api/history");
  return result(data, error);
}
