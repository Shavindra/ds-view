import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/source-serif-4/latin-500.css";
import "@fontsource/source-serif-4/latin-600.css";
import "./style.css";
import { Detail } from "./Detail";
import { searchable, type Entry, type Project, type Section } from "./model";
import { openProject, read } from "./reader";

const sections: Section[] = ["Papers", "Datasets", "Records"];

function Library({project, open, refresh, pending}: {project: Project; open: () => void; refresh: () => void; pending: boolean}) {
  const [section, setSection] = useState<Section>(sections.find(s => project.records.some(r => r.section === s)) ?? "Papers");
  const [selection, setSelection] = useState("");
  const [filter, setFilter] = useState("");
  const [tag, setTag] = useState("");
  const [query, setQuery] = useState("");
  const [matches, setMatches] = useState<{term: string; ids: Set<string>}>();
  const [searchError, setSearchError] = useState("");
  const globalInput = useRef<HTMLInputElement>(null);
  const sidebar = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault(); globalInput.current?.focus();
      }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, []);
  const term = query.trim().toLowerCase();
  useEffect(() => {
    setSearchError("");
    if (!term) return;
    let active = true;
    const timer = window.setTimeout(() => {
      read<string[]>({op: "search", session: project.session, term}).then(ids => {
        if (active) setMatches({term, ids: new Set(ids)});
      }, error => { if (active) setSearchError(String(error)); });
    }, 160);
    return () => { active = false; clearTimeout(timer); };
  }, [term, project.session]);

  const records = project.records.filter(r => r.section === section);
  const tags = Array.from(new Set(records.flatMap(r => r.labels))).sort();
  const shown = records.filter(r => (!term || searchable(r).includes(term) || (matches?.term === term && matches.ids.has(r.id))) &&
    searchable(r).includes(filter.trim().toLowerCase()) && (!tag || r.labels.includes(tag)));
  const selected = shown.find(r => r.id === selection) ?? shown[0];
  const changeSection = (next: Section) => {
    setSection(next); setSelection(""); setFilter(""); setTag("");
    sidebar.current?.scrollTo(0,0);
  };
  const navigate = (entry: Entry) => {
    changeSection(entry.section); setQuery(""); setSelection(entry.id);
  };
  const groupCounts = new Map(sections.map(s => [s, project.records.filter(r => r.section === s).length]));
  const isSearching = term && matches?.term !== term && !searchError;
  return <><header className="topbar"><div className="brand">
    {project.brand.logo ? <img src={project.brand.logo} alt=""/> : <i className="dot"/>}{project.brand.app_name}</div>
    <nav aria-label="Catalogue sections">{sections.filter(s => groupCounts.get(s)).map(s =>
      <button key={s} onClick={() => changeSection(s)} aria-current={section === s ? "page" : undefined}>{s}<small>{groupCounts.get(s)}</small></button>)}</nav>
    <div className="actions"><input ref={globalInput} type="search" aria-label="Search catalogue" placeholder="Search papers, datasets, files" value={query} onChange={e => setQuery(e.target.value)}/>
      <button className="header-action" onClick={refresh} disabled={pending}>Refresh</button><button className="header-action" onClick={open} disabled={pending}>Open folder</button></div></header>
    {(pending || searchError || project.warnings.length > 0) && <div className="notice" role="status">{pending && "Reading project…"}{searchError}
      {project.warnings.length > 0 && <details><summary>{project.warnings.length} metadata {project.warnings.length === 1 ? "warning" : "warnings"}</summary>{project.warnings.map((w, i) => <p key={i}>{w}</p>)}</details>}</div>}
    <div className="layout"><aside className="sidebar" aria-label="Records"><div className="tools">
      <div className="caption">{section}<small>{shown.length}</small></div>
      <input type="search" aria-label="Filter records" placeholder={section === "Papers" ? "Filter by title, author, PID" : "Filter by name, PID, format"} value={filter} onChange={e => setFilter(e.target.value)}/>
      {tags.length > 0 && <div className="chips">{["", ...tags].map(t => <button key={t} aria-pressed={t === tag} onClick={() => setTag(t)}>{t || "All"}</button>)}</div>}
    </div><div className="record-list" ref={sidebar}>{shown.map(r => <button className="record-row" key={r.id} aria-pressed={r.id === selected?.id}
        onClick={() => setSelection(r.id)}><b className={r.section === "Papers" ? "serif" : ""}>{r.title}</b>
        {(r.primaryAuthor || r.venue || r.year) && <span className="row-byline">{[r.primaryAuthor, r.venue, r.year].filter(Boolean).join(" · ")}</span>}
        <span>{r.section === "Papers" ? (() => { const count = project.records.filter(other => other.section === "Datasets" && Object.hasOwn(r.links, other.id)).length; return count + (count === 1 ? " dataset" : " datasets"); })() : r.format || r.kind}
        {r.labels.map(t => <em key={t}>{t}</em>)}</span></button>)}</div></aside>
      {selected ? <Detail key={selected.id} entry={selected} records={project.records} session={project.session} navigate={navigate}/> :
        <main className="empty-results"><h2>{!project.records.length ? "No metadata found" : isSearching ? "Searching…" : "No matching records"}</h2>
          <p>{!project.records.length ? "Choose a folder containing a catalogue or a DataLad metadata store." : "Try another search or filter."}</p></main>}
    </div></>;
}

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const busy = useRef(false);
  const run = useCallback(async (action: () => Promise<Project | null>) => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError("");
    try {
      const result = await action();
      if (result) {
        setProject(result);
        document.title = result.name + " · " + (result.brand.page_title === "shaclpy" ? "DS View" : result.brand.page_title);
      }
    } catch (reason) { setError(String(reason)); }
    finally { busy.current = false; setPending(false); }
  }, []);
  const open = useCallback(() => run(() => openProject()), [run]);
  useEffect(() => { void run(() => openProject(true)); }, [run]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "o") { event.preventDefault(); void open(); }
    };
    window.addEventListener("keydown", keydown); return () => window.removeEventListener("keydown", keydown);
  }, [open]);
  return <>{error && <div className="error" role="alert"><span>{error}</span><button onClick={() => setError("")}>Dismiss</button></div>}
    {project ? <Library key={project.root} project={project} open={open} pending={pending}
      refresh={() => run(() => read<Project>({op: "refresh", session: project.session}))}/> :
      <><header className="topbar"><div className="brand"><i className="dot"/>DS View</div></header>
        <main className="welcome"><div><h1>Open a project</h1><p>Browse papers, datasets and files in a DataLad project or local metadata catalogue.</p>
          <button className="primary" disabled={pending} onClick={open}>{pending ? "Opening…" : "Open project folder"}</button></div></main></>}
  </>;
}

createRoot(document.getElementById("root")!).render(<App/>);
