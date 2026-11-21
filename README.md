# DS View

A read-only desktop viewer for DataLad projects and DataLad Concepts catalogues on macOS and Windows. Open a project folder to browse its papers, linked datasets, files and original metadata.

DS View uses a shared React and TypeScript interface in Tauri. Its bundled Python reader uses [shacl-py](https://github.com/Shavindra/shacl-py) and the [DataLad MetaLad API](https://docs.datalad.org/projects/metalad/en/stable/generated/datalad.api.meta_dump.html). See the [DataLad Concepts Toolkit](https://concepts.datalad.org/) and [shacl-vue](https://github.com/psychoinformatics-de/shacl-vue) for the original schema and viewer projects.

## Install

Download the build for your platform from the latest successful [desktop build](https://github.com/Shavindra/ds-view/actions/workflows/build.yml). Unzip the downloaded artifact. On macOS (Apple Silicon), open the DMG and drag DS View into Applications. On Windows (x64), run the setup executable. These development builds are unsigned. The Windows installer handles WebView2 when needed.

Choose **Open project folder** to browse the catalogue. The app includes Python, DataLad, MetaLad and a private Git executable for reading metadata. It works independently of other DataLad or Git installations. The viewer reads stored dataset and file metadata, shows local availability and never runs `datalad get`. Use **Refresh** to reread the project after changing metadata with the CLI.

## Build from source

Install Node.js 22.12 or later, Python 3.14, Git and stable Rust with Cargo. On macOS, install the Xcode Command Line Tools with `xcode-select --install` if needed. On Windows, install the Microsoft C++ Build Tools as described in the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

Install Rust with [rustup](https://rustup.rs/), then open a new terminal. If Rust is already installed on macOS, `. "$HOME/.cargo/env"` loads the default rustup installation into the current shell. Check the toolchain and build from the repository root.

```sh
rustc --version
cargo --version
npm ci
npm run desktop
```

Both `npm run desktop` and `npm run package` fetch the current commit of [shacl-py main](https://github.com/Shavindra/shacl-py/tree/main) and build the reader in `.reader-build/venv`. You can run either command from an active Conda or Python environment. Each build prints the full Git commit, verifies it in the compiled reader and saves it in `.reader-build/shacl-py-commit.txt`. Source builds require access to GitHub. Installed apps use their bundled reader offline.

Use `npm run package -- --bundles dmg` on macOS or `npm run package -- --bundles nsis` on Windows. The installer goes in `src-tauri/target/release/bundle/`. GitHub Actions selects one upstream commit for both platforms, links it in the run summary and checks each installed reader against that commit and a real MetaLad store.

The record relationships, source grouping, catalogue validation and file selection come from shacl-py. React handles navigation, raw metadata views and file previews. The app bundles IBM Plex Sans, IBM Plex Mono and Source Serif 4 for offline use. The project can customise the header through its existing `.shacl-py/config.yaml`.

The embedded Git build comes from [Dugite Native 2.56.1](https://github.com/desktop/dugite-native/tree/v2.56.1). Its matching sources are [Git](https://github.com/git/git/tree/v2.56.1) and [Git for Windows](https://github.com/git-for-windows/git). The app includes the [Git licence](licenses/git-COPYING.txt).
