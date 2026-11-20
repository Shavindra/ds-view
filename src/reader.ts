import { invoke } from "@tauri-apps/api/core";
import { useEffect, useState } from "react";
import type { Project } from "./model";

export function openProject(initial = false) {
  return invoke<Project | null>("open_project", { initial });
}

export function read<T>(query: Record<string, unknown>) {
  return invoke<T>("read_project", { query });
}

// An older response must never replace a newly selected folder or project.
export function useQuery<T>(query: Record<string, unknown>) {
  const key = JSON.stringify(query);
  const [result, setResult] = useState<{key: string; data?: T; error?: string}>();
  useEffect(() => {
    let active = true;
    read<T>(JSON.parse(key)).then(
      data => { if (active) setResult({key, data}); },
      error => { if (active) setResult({key, error: String(error)}); }
    );
    return () => { active = false; };
  }, [key]);
  return result?.key === key ? result : undefined;
}
