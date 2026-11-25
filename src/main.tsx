import { invoke } from "@tauri-apps/api/core";
import { openUrl } from "@tauri-apps/plugin-opener";
import { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/source-serif-4/latin-600.css";
import "./style.css";

interface Project {
  name: string;
  title: string;
  url: string;
}

function App() {
  const [project, setProject] = useState<Project | null>(null);
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const frame = useRef<HTMLIFrameElement>(null);
  const busy = useRef(false);

  const open = useCallback(async (initial = false) => {
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    setError("");
    try {
      const next = await invoke<Project | null>("open_project", { initial });
      if (next) {
        const address = new URL(next.url);
        if (
          address.protocol !== "http:" ||
          address.hostname !== "127.0.0.1" ||
          !address.port
        ) {
          throw new Error("The viewer returned an invalid project address.");
        }
        setReady(false);
        setProject(next);
        document.title = `${next.name} · ${next.title === "shaclpy" ? "DS View" : next.title}`;
      }
    } catch (reason) {
      setError(String(reason));
    } finally {
      busy.current = false;
      setPending(false);
    }
  }, []);
  useEffect(() => {
    void open(true);
  }, [open]);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "o") {
        event.preventDefault();
        void open();
      }
    }
    function onMessage(event: MessageEvent) {
      if (
        !project ||
        event.source !== frame.current?.contentWindow ||
        event.origin !== new URL(project.url).origin ||
        event.data?.source !== "ds-view"
      )
        return;
      if (event.data.action === "ready") setReady(true);
      if (event.data.action === "open") void open();
      if (
        event.data.action === "external" &&
        typeof event.data.value === "string" &&
        /^https?:\/\//i.test(event.data.value)
      ) {
        openUrl(event.data.value).catch((reason) => setError(String(reason)));
      }
    }
    window.addEventListener("keydown", onKey);
    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("message", onMessage);
    };
  }, [open, project]);
  function refresh() {
    if (project)
      frame.current?.contentWindow?.postMessage(
        { source: "ds-view", action: "refresh" },
        new URL(project.url).origin,
      );
  }
  return (
    <>
      <header className="topbar">
        <strong>DS View</strong>
        {project && (
          <>
            <span className="project-name">{project.name}</span>
            <button disabled={pending} onClick={() => void open()}>
              Open project folder
            </button>
            <button disabled={!ready || pending} onClick={refresh}>
              Refresh
            </button>
          </>
        )}
      </header>
      {error && (
        <div className="error" role="alert">
          {error}
          <button onClick={() => setError("")}>Dismiss</button>
        </div>
      )}
      {project ? (
        <iframe
          key={project.url}
          ref={frame}
          title="Project catalogue"
          src={project.url + "?embed=true"}
          sandbox="allow-scripts allow-same-origin allow-forms"
        />
      ) : (
        <main className="welcome">
          <div>
            <h1>Open a project</h1>
            <p>
              Browse papers, datasets and files in a DataLad project or local
              metadata catalogue.
            </p>
            <button
              className="primary"
              disabled={pending}
              onClick={() => void open()}
            >
              {pending ? "Opening…" : "Open project folder"}
            </button>
          </div>
        </main>
      )}
    </>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
