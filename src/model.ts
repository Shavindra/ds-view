export type Section = "Papers" | "Datasets" | "Records";
export type Page = "Datasets" | "Abstract" | "Notes" | "Other files" | "Files" | "Papers" | "Related" | "Raw metadata";

export interface Entry {
  id: string;
  section: Section;
  title: string;
  kind: string;
  pid: string;
  folder: string;
  primaryAuthor: string;
  authors: string;
  venue: string;
  year: string;
  abstract: string;
  notes: string;
  format: string;
  labels: string[];
  keywords: string;
  url: string;
  urlLabel: string;
  links: Record<string, string>;
}

export interface Project {
  session: string;
  name: string;
  root: string;
  brand: {app_name: string; page_title: string; logo: string};
  warnings: string[];
  records: Entry[];
}

export interface FileRow {path: string; size: number | null; local: boolean}
export interface Listing {folders: string[]; rows: FileRow[]}
export interface FileDetail {metadata: unknown[]; preview: string | null; truncated: boolean; canPreview: boolean}
export interface Source {name: string; fields: string; source: string}

export function pages(entry: Entry): Page[] {
  if (entry.section === "Papers") return ["Datasets", "Abstract", "Notes", "Other files", "Raw metadata"];
  if (entry.section === "Datasets") return ["Files", "Papers", "Raw metadata"];
  return ["Related", "Files", "Raw metadata"];
}

export function searchable(entry: Entry): string {
  return [entry.title, entry.kind, entry.pid, entry.folder, entry.authors, entry.venue,
    entry.year, entry.format, entry.abstract, entry.notes, entry.keywords, ...entry.labels]
    .join(" ").toLowerCase();
}

export function sizeLabel(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KiB`;
  if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MiB`;
  return `${(bytes / 1073741824).toFixed(1)} GiB`;
}
