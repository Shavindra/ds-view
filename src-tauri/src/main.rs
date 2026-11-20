#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

struct Reader {
    process: Child,
    input: ChildStdin,
    output: BufReader<ChildStdout>,
}

impl Reader {
    fn start() -> Result<Self, String> {
        let path = std::env::current_exe()
            .map_err(|error| error.to_string())?
            .with_file_name(format!("ds-reader{}", std::env::consts::EXE_SUFFIX));
        let mut command = Command::new(&path);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        let mut process = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|error| {
                format!(
                    "Could not start the metadata reader at {}: {error}",
                    path.display()
                )
            })?;
        let input = process.stdin.take().expect("piped stdin");
        let output = BufReader::new(process.stdout.take().expect("piped stdout"));
        Ok(Self {
            process,
            input,
            output,
        })
    }

    fn exchange(&mut self, message: &Value) -> Result<Value, String> {
        writeln!(self.input, "{message}")
            .and_then(|_| self.input.flush())
            .map_err(|e| e.to_string())?;
        let mut line = String::new();
        if self
            .output
            .read_line(&mut line)
            .map_err(|e| e.to_string())?
            == 0
        {
            return Err("The metadata reader stopped. Reopen the project to retry.".to_owned());
        }
        serde_json::from_str(&line)
            .map_err(|e| format!("Invalid response from the metadata reader: {e}"))
    }
}

impl Drop for Reader {
    fn drop(&mut self) {
        // EOF lets the bundled Python runtime clean up its temporary directory.
        let _ = self.input.write_all(b"{\"op\":\"quit\"}\n");
        let _ = self.input.flush();
        let _ = self.process.wait();
    }
}

#[derive(Default)]
struct Backend(Mutex<Option<Reader>>);

fn request(app: &AppHandle, message: Value) -> Result<Value, String> {
    let backend = app.state::<Backend>();
    let mut slot = backend.0.lock().map_err(|_| "Reader lock unavailable")?;
    if slot.is_none() {
        *slot = Some(Reader::start()?);
    }
    let response = match slot.as_mut().expect("initialised").exchange(&message) {
        Ok(response) => response,
        Err(error) => {
            slot.take();
            return Err(error);
        }
    };
    if let Some(error) = response.get("error").and_then(Value::as_str) {
        return Err(error.to_owned());
    }
    response
        .get("value")
        .cloned()
        .ok_or_else(|| "Missing reader response".to_owned())
}

#[derive(Deserialize, Serialize)]
#[serde(tag = "op", rename_all = "snake_case")]
enum Query {
    Search {
        session: String,
        term: String,
    },
    Refresh {
        session: String,
    },
    Files {
        session: String,
        id: String,
        folder: String,
    },
    File {
        session: String,
        id: String,
        folder: String,
        path: String,
        preview: bool,
    },
    Source {
        session: String,
        id: String,
    },
}

#[tauri::command]
async fn read_project(app: AppHandle, query: Query) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || request(&app, json!(query)))
        .await
        .map_err(|e| e.to_string())?
}

#[derive(Default)]
struct InitialFolder(Mutex<Option<PathBuf>>);

#[tauri::command]
async fn open_project(app: AppHandle, initial: bool) -> Result<Option<Value>, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let path = if initial {
            app.state::<InitialFolder>()
                .0
                .lock()
                .map_err(|_| "Folder lock unavailable")?
                .take()
        } else {
            app.dialog()
                .file()
                .set_title("Open project folder")
                .blocking_pick_folder()
                .map(|path| path.into_path().map_err(|e| e.to_string()))
                .transpose()?
        };
        path.map(|root| request(&app, json!({"op":"open","root":root})))
            .transpose()
    })
    .await
    .map_err(|e| e.to_string())?
}

fn main() {
    let initial = std::env::args_os()
        .nth(1)
        .map(PathBuf::from)
        .filter(|p| p.is_dir());
    let app = tauri::Builder::default()
        .manage(Backend::default())
        .manage(InitialFolder(Mutex::new(initial)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![open_project, read_project])
        .build(tauri::generate_context!())
        .expect("could not start DS View");
    app.run(|app, event| {
        if let tauri::RunEvent::Exit = event {
            if let Ok(mut reader) = app.state::<Backend>().0.lock() {
                reader.take();
            }
        }
    });
}
