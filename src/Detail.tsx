import { useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import { Files } from "./Files";
import { pages, type Entry, type Page, type Source } from "./model";
import { useQuery } from "./reader";

type Navigate = (entry: Entry) => void;

function Sources({ session, entry }: { session: string; entry: Entry }) {
  const result = useQuery<Source[]>({ op: "source", session, id: entry.id });
  if (result?.error) return <p role="alert">{result.error}</p>;
  if (!result?.data) return <p role="status">Reading metadata…</p>;
  return (
    <>
      {result.data.map((src, index) => (
        <section key={index} className="source">
          <h3>{src.name}</h3>
          <pre>{src.fields}</pre>
          {src.fields !== src.source && (
            <details>
              <summary>Full source metadata</summary>
              <pre>{src.source}</pre>
            </details>
          )}
        </section>
      ))}
    </>
  );
}

function Facts({ entry }: { entry: Entry }) {
  return (
    <dl className="facts">
      {[
        ["PID", entry.pid],
        ["Folder", entry.folder],
        ["Format", entry.format],
      ]
        .filter(([, value]) => value)
        .map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
    </dl>
  );
}

function LinkedDatasets({
  entry,
  records,
  session,
  navigate,
}: {
  entry: Entry;
  records: Entry[];
  session: string;
  navigate: Navigate;
}) {
  const [selected, setSelected] = useState("");
  const [filter, setFilter] = useState("");
  const datasets = records.filter((r) =>
    r.title.toLowerCase().includes(filter.toLowerCase()),
  );
  const dataset = datasets.find((r) => r.id === selected) ?? datasets[0];
  return (
    <div className="dataset-split">
      <aside className="dataset-list" aria-label="Linked datasets">
        <input
          type="search"
          aria-label="Filter datasets"
          placeholder="Filter datasets"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        {datasets.map((r) => (
          <button
            key={r.id}
            className="record-row"
            aria-pressed={dataset?.id === r.id}
            onClick={() => setSelected(r.id)}
          >
            <b>{r.title}</b>
            <span>{entry.links[r.id]}</span>
          </button>
        ))}
      </aside>
      <article>
        {dataset ? (
          <>
            <div className="dataset-heading">
              <h2>{dataset.title}</h2>
              <button className="text-button" onClick={() => navigate(dataset)}>
                Open in Datasets →
              </button>
            </div>
            <Facts entry={dataset} />
            <Files
              key={dataset.id + session}
              session={session}
              entry={dataset}
            />
          </>
        ) : (
          <p>{filter ? "No matching datasets." : "No linked datasets."}</p>
        )}
      </article>
    </div>
  );
}

export function Detail({
  entry,
  records,
  session,
  navigate,
}: {
  entry: Entry;
  records: Entry[];
  session: string;
  navigate: Navigate;
}) {
  const options = pages(entry);
  const [page, setPage] = useState<Page>(options[0]);
  const [linkError, setLinkError] = useState("");
  const linked = records.filter((r) => Object.hasOwn(entry.links, r.id));
  const datasets = linked.filter((r) => r.section === "Datasets");
  const papers = linked.filter((r) => r.section === "Papers");
  const follow = (url: string) => {
    if (/^https?:\/\//i.test(url))
      openUrl(url).catch((e) => setLinkError(String(e)));
  };
  return (
    <main className="detail">
      <div className="heading">
        {(entry.pid || entry.folder) && (
          <div className="locator">
            {[entry.pid, entry.folder].filter(Boolean).join("　/　")}
          </div>
        )}
        <h1 className={entry.section === "Papers" ? "serif" : ""}>
          {entry.title}
        </h1>
        {entry.section === "Datasets" ? (
          <Facts entry={entry} />
        ) : (
          <>
            {(entry.authors || entry.venue || entry.year) && (
              <div className="byline">
                {[entry.authors, entry.venue, entry.year]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            )}
            {(entry.labels.length > 0 || entry.keywords || entry.url) && (
              <div className="inline">
                {entry.labels.map((tag) => (
                  <em key={tag}>{tag}</em>
                ))}
                {entry.url && (
                  <button
                    className="text-button"
                    onClick={() => follow(entry.url)}
                  >
                    {entry.urlLabel}
                  </button>
                )}
                {entry.keywords && <span>{entry.keywords}</span>}
              </div>
            )}
            {linkError && <p role="alert">{linkError}</p>}
          </>
        )}
        <nav className="tabs" aria-label="Record views">
          {options.map((p) => (
            <button
              key={p}
              aria-current={page === p ? "page" : undefined}
              onClick={() => setPage(p)}
            >
              {p}
              {p === "Datasets" && <small>{datasets.length}</small>}
            </button>
          ))}
        </nav>
      </div>
      {page === "Datasets" ? (
        <LinkedDatasets
          entry={entry}
          records={datasets}
          session={session}
          navigate={navigate}
        />
      ) : (
        <article>
          {(page === "Files" || page === "Other files") && (
            <Files entry={entry} session={session} />
          )}
          {page === "Abstract" && (
            <p className="abstract serif">
              {entry.abstract || "No abstract supplied."}
            </p>
          )}
          {page === "Notes" && (
            <div className="notes">{entry.notes || "No notes supplied."}</div>
          )}
          {page === "Raw metadata" && (
            <Sources session={session} entry={entry} />
          )}
          {(page === "Papers" || page === "Related") && (
            <>
              {(page === "Papers" ? papers : linked).map((r) => (
                <button
                  className="related-row"
                  key={r.id}
                  onClick={() => navigate(r)}
                >
                  <b>{r.title}</b>
                  <small>{entry.links[r.id] || r.kind}</small>
                </button>
              ))}
              {!(page === "Papers" ? papers : linked).length && (
                <p>No linked records.</p>
              )}
            </>
          )}
        </article>
      )}
    </main>
  );
}
