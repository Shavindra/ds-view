#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;

#[derive(Deserialize, Serialize)]
struct Project {
    name: String,
    title: String,
    url: String,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum Ready {
    Project(Project),
    Error { error: String },
}

struct Viewer(Child);

impl Viewer {
    fn open(root: PathBuf) -> Result<(Self, Project), String> {
        let path = std::env::current_exe()
            .map_err(|e| e.to_string())?
            .with_file_name(format!("ds-reader{}", std::env::consts::EXE_SUFFIX));
        let mut command = Command::new(path);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        let mut viewer = Self(
            command
                .arg("--view")
                .arg(root)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::inherit())
                .spawn()
                .map_err(|e| format!("Could not start the catalogue viewer: {e}"))?,
        );
        let mut line = String::new();
        let output = viewer.0.stdout.take().expect("piped stdout");
        if BufReader::new(output)
            .read_line(&mut line)
            .map_err(|e| e.to_string())?
            == 0
        {
            return Err("The catalogue viewer stopped before opening the project.".into());
        }
        match serde_json::from_str(&line).map_err(|e| format!("Invalid viewer response: {e}"))? {
            Ready::Project(project) => Ok((viewer, project)),
            Ready::Error { error } => Err(error),
        }
    }
}

impl Drop for Viewer {
    fn drop(&mut self) {
        // EOF asks the viewer to close its sockets and clean up its frozen runtime.
        drop(self.0.stdin.take());
        let deadline = Instant::now() + Duration::from_secs(8);
        while Instant::now() < deadline {
            match self.0.try_wait() {
                Ok(Some(_)) => return,
                Ok(None) => std::thread::sleep(Duration::from_millis(50)),
                Err(_) => break,
            }
        }
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}

#[derive(Default)]
struct CurrentViewer(Mutex<Option<Viewer>>);

#[derive(Default)]
struct InitialFolder(Mutex<Option<PathBuf>>);

#[tauri::command]
async fn open_project(app: AppHandle, initial: bool) -> Result<Option<Project>, String> {
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
        let Some(root) = path else { return Ok(None) };
        // Keep the open project usable when the picker is cancelled or the new viewer fails.
        let (viewer, project) = Viewer::open(root)?;
        let previous = app
            .state::<CurrentViewer>()
            .0
            .lock()
            .map_err(|_| "Viewer lock unavailable")?
            .replace(viewer);
        drop(previous);
        Ok(Some(project))
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
        .manage(CurrentViewer::default())
        .manage(InitialFolder(Mutex::new(initial)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![open_project])
        .build(tauri::generate_context!())
        .expect("could not start DS View");
    app.run(|app, event| {
        if let tauri::RunEvent::Exit = event {
            if let Ok(mut viewer) = app.state::<CurrentViewer>().0.lock() {
                viewer.take();
            }
        }
    });
}
