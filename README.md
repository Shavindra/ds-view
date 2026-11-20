# DS View

A read-only desktop viewer for DataLad projects and DataLad Concepts catalogues on macOS and Windows. Open a project folder to browse its papers, linked datasets, files and original metadata.

DS View uses a shared React and TypeScript interface in Tauri. Its bundled Python reader uses [shacl-py](https://github.com/Shavindra/shacl-py) and the [DataLad MetaLad API](https://docs.datalad.org/projects/metalad/en/stable/generated/datalad.api.meta_dump.html). See the [DataLad Concepts Toolkit](https://concepts.datalad.org/) and [shacl-vue](https://github.com/psychoinformatics-de/shacl-vue) for the original schema and viewer projects.

## Install

Download the build for your platform from the latest successful [desktop build](https://github.com/Shavindra/ds-view/actions/workflows/build.yml). Unzip the downloaded artifact. On macOS (Apple Silicon), open the DMG and drag DS View into Applications. On Windows (x64), run the setup executable. These development builds are unsigned. The Windows installer handles WebView2 when needed.

Choose **Open project folder** to browse the catalogue. The reader and its Python runtime ship with the app. Reading a live MetaLad store also uses Git on the system path. The viewer reads stored dataset and file metadata, shows local availability and never runs `datalad get`. Use **Refresh** to reread the project after changing metadata with the CLI.

## Development

Use Node.js 22.12 or later, standard Python 3.14, Git, and the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) for your platform. Activate a Python virtual environment in the checkout, then run:

```sh
npm ci
python scripts/build_reader.py
npm run desktop
```

Use `npm run package -- --bundles dmg` on macOS or `npm run package -- --bundles nsis` on Windows. The installer goes in `src-tauri/target/release/bundle/`. The GitHub workflow builds the helper for each platform, tests the shared layout and verifies the reader inside the packaged app against a real MetaLad store.

The record relationships, source grouping, catalogue validation and file selection come from a pinned version of shacl-py. React handles navigation, raw metadata views and file previews. The app bundles IBM Plex Sans, IBM Plex Mono and Source Serif 4 for offline use. The project can customise the header through its existing `.shacl-py/config.yaml`.
