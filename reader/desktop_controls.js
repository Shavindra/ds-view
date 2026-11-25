export default function ({ parentElement }) {
  parentElement.desktopListeners?.abort();
  const listeners = new AbortController();
  parentElement.desktopListeners = listeners;
  const options = { signal: listeners.signal };
  const send = (action, value) =>
    parent.postMessage({ source: "ds-view", action, value }, "*");

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest?.('a[target="_blank"]');
      if (!link) return;
      event.preventDefault();
      const url = new URL(link.href, location.href);
      if (["https:", "http:"].includes(url.protocol))
        send("external", url.href);
    },
    options,
  );
  document.addEventListener(
    "keydown",
    (event) => {
      if (!(event.metaKey || event.ctrlKey)) return;
      if (event.key.toLowerCase() === "o") {
        event.preventDefault();
        send("open");
      } else if (event.key.toLowerCase() === "f") {
        event.preventDefault();
        document.querySelector('.study header input[type="search"]')?.focus();
      }
    },
    options,
  );
  window.addEventListener(
    "message",
    (event) => {
      if (
        event.source === parent &&
        event.data?.source === "ds-view" &&
        event.data.action === "refresh"
      ) {
        location.reload();
      }
    },
    options,
  );
  send("ready");
  return () => listeners.abort();
}
