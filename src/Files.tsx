import { useState } from "react";
import { useQuery } from "./reader";
import {
  sizeLabel,
  type Entry,
  type FileDetail,
  type FileRow,
  type Listing,
} from "./model";

function FileInspector({
  session,
  entry,
  folder,
  row,
  close,
}: {
  session: string;
  entry: Entry;
  folder: string;
  row: FileRow;
  close: () => void;
}) {
  const [preview, setPreview] = useState(false);
  const result = useQuery<FileDetail>({
    op: "file",
    session,
    id: entry.id,
    folder,
    path: row.path,
    preview,
  });
  return (
    <section className="inspector" aria-label="File details">
      <button className="text-button" onClick={close}>
        ← Files
      </button>
      <h3>{row.path.split("/").at(-1)}</h3>
      <dl>
        <dt>Path</dt>
        <dd>{row.path}</dd>
        <dt>Availability</dt>
        <dd>{row.local ? "Local" : "Unavailable locally"}</dd>
      </dl>
      {result?.error && <p role="alert">{result.error}</p>}
      {result?.data && (
        <>
          {result.data.metadata.length > 0 && (
            <>
              <h4>File metadata</h4>
              <pre>{JSON.stringify(result.data.metadata, null, 2)}</pre>
            </>
          )}
          {!preview && result.data.canPreview && (
            <button className="button" onClick={() => setPreview(true)}>
              Preview text
            </button>
          )}
          {preview &&
            (result.data.preview !== null ? (
              <>
                <pre>{result.data.preview}</pre>
                {result.data.truncated && <small>First 8 KiB</small>}
              </>
            ) : (
              <p>A text preview is unavailable for this file.</p>
            ))}
        </>
      )}
    </section>
  );
}

export function Files({ session, entry }: { session: string; entry: Entry }) {
  const [folder, setFolder] = useState(".");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<FileRow | null>(null);
  const result = useQuery<Listing>({
    op: "files",
    session,
    id: entry.id,
    folder,
  });
  const rows = result?.data?.rows ?? [];
  const matches = (name: string) =>
    name.toLowerCase().includes(filter.toLowerCase());
  const folders = (result?.data?.folders ?? []).filter(matches);
  const displayRows = rows.filter((r) => matches(r.path));
  const move = (next: string) => {
    setSelected(null);
    setFilter("");
    setFolder(next);
  };
  return (
    <>
      <section className="filebox" aria-label="Files">
        <div className="filebar">
          <h3>Files {result?.data && <small>{rows.length}</small>}</h3>
          <input
            type="search"
            aria-label="Find file"
            placeholder="Find file"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        {folder !== "." && (
          <button
            className="folder"
            onClick={() =>
              move(folder.split("/").slice(0, -1).join("/") || ".")
            }
          >
            ↑ Parent folder
          </button>
        )}
        {result?.error ? (
          <p role="alert">{result.error}</p>
        ) : !result?.data ? (
          <p role="status">Reading files…</p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Path</th>
                  <th>Size</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {folders.map((dir) => (
                  <tr key={dir}>
                    <td colSpan={4}>
                      <button className="folder" onClick={() => move(dir)}>
                        {dir.split("/").at(-1)} /
                      </button>
                    </td>
                  </tr>
                ))}
                {displayRows.map((row) => (
                  <tr key={row.path}>
                    <td>
                      <button
                        className="filelink"
                        title={row.path}
                        onClick={() => setSelected(row)}
                      >
                        {row.path.split("/").at(-1)}
                      </button>
                    </td>
                    <td title={row.path}>
                      {row.path.split("/").slice(0, -1).join("/") || "."}
                    </td>
                    <td>{sizeLabel(row.size)}</td>
                    <td className="status">
                      <span aria-hidden="true">{row.local ? "●" : "○"}</span>{" "}
                      {row.local ? "Local" : "Not local"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!folders.length && !displayRows.length && (
              <p>
                {filter ? "No files match your search." : "No files listed."}
              </p>
            )}
            {rows.length > 0 && (
              <footer>
                {rows.filter((r) => r.local).length} of {rows.length} files
                local
              </footer>
            )}
          </>
        )}
      </section>
      {selected && (
        <FileInspector
          key={selected.path}
          entry={entry}
          session={session}
          row={selected}
          folder={folder}
          close={() => setSelected(null)}
        />
      )}
    </>
  );
}
