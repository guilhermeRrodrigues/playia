use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

struct SidecarHandle(Mutex<Option<Child>>);

fn locate_uv() -> Option<PathBuf> {
    if let Ok(p) = which::which("uv") {
        return Some(p);
    }
    for candidate in [
        "/opt/homebrew/bin/uv",
        "/usr/local/bin/uv",
        "C:\\Program Files\\uv\\uv.exe",
    ] {
        let p = PathBuf::from(candidate);
        if p.exists() {
            return Some(p);
        }
    }
    None
}

fn locate_backend_dir() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    cwd.join("..").join("backend")
}

fn spawn_sidecar() -> std::io::Result<Child> {
    let uv = locate_uv().ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "uv não encontrado no PATH nem nos fallbacks padrão",
        )
    })?;
    let backend = locate_backend_dir();
    log::info!(
        "spawning sidecar: {} run python main.py (cwd={})",
        uv.display(),
        backend.display()
    );
    Command::new(uv)
        .args(["run", "python", "main.py"])
        .current_dir(backend)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().build())
        .setup(|app| {
            match spawn_sidecar() {
                Ok(child) => {
                    log::info!("sidecar spawned, pid={}", child.id());
                    app.manage(SidecarHandle(Mutex::new(Some(child))));
                }
                Err(e) => {
                    log::error!("falha ao subir sidecar: {e}");
                    app.manage(SidecarHandle(Mutex::new(None)));
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                if let Some(state) = app_handle.try_state::<SidecarHandle>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            log::info!("matando sidecar pid={}", child.id());
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        });
}
