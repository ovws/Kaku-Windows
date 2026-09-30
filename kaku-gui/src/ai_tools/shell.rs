//! Shell execution tools: shell_exec, shell_bg, shell_poll.

use anyhow::{Context, Result};
use std::collections::HashMap;
use std::io::Read;
#[cfg(unix)]
use std::os::unix::fs::OpenOptionsExt;
#[cfg(unix)]
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};

use super::paths::resolve;

/// Wall-clock ceiling for a single `shell_exec` invocation.
pub(super) const SHELL_EXEC_TIMEOUT_SECS: u64 = 60;

/// Kill the entire process tree. Required because `Child::kill()` only
/// signals the direct child (the login shell), leaving grandchildren running.
pub(super) fn kill_process_group(child: &std::process::Child) {
    #[cfg(unix)]
    unsafe {
        libc::killpg(child.id() as libc::pid_t, libc::SIGKILL);
    }
    #[cfg(windows)]
    {
        // Kill descendants too; Child::kill alone would leave shell jobs alive.
        let _ = std::process::Command::new("taskkill.exe")
            .args(["/F", "/T", "/PID", &child.id().to_string()])
            .creation_flags(0x08000000)
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status();
    }
}

#[cfg(unix)]
fn shell_exec_wrapper(command: &str, cwd_tmp_path: &Path, shell: &str) -> String {
    let is_fish = Path::new(shell)
        .file_name()
        .and_then(|name| name.to_str())
        .is_some_and(|name| name == "fish");

    if is_fish {
        format!(
            "{}; set __kaku_rc $status; printf '%s' (pwd) > {}; exit $__kaku_rc",
            command,
            cwd_tmp_path.display()
        )
    } else {
        format!(
            "{}; __kaku_rc=$?; printf '%s' \"$(pwd)\" > {}; exit $__kaku_rc",
            command,
            cwd_tmp_path.display()
        )
    }
}

#[cfg(windows)]
use std::os::windows::process::CommandExt;

fn default_shell() -> String {
    #[cfg(unix)]
    {
        std::env::var("SHELL").unwrap_or_else(|_| "/bin/bash".into())
    }
    #[cfg(windows)]
    {
        "powershell.exe".into()
    }
}

fn shell_command(shell: &str, command: &str) -> std::process::Command {
    let mut cmd = std::process::Command::new(shell);
    #[cfg(unix)]
    cmd.args(["-l", "-c", command]);
    #[cfg(windows)]
    cmd.args([
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        command,
    ]);
    cmd
}

pub(super) fn configure_process(cmd: &mut std::process::Command) {
    #[cfg(unix)]
    cmd.process_group(0);
    #[cfg(windows)]
    cmd.creation_flags(0x08000000);
}

#[cfg(windows)]
fn shell_exec_wrapper(command: &str, cwd_tmp_path: &Path, _shell: &str) -> String {
    let path = cwd_tmp_path.to_string_lossy().replace("\u{27}", "''");
    format!(
        "$global:LASTEXITCODE = 0; & {{ {} }}; $__kaku_ok = $?;          $__kaku_rc = $LASTEXITCODE;          [System.IO.File]::WriteAllText('{}', (Get-Location).Path,          [System.Text.UTF8Encoding]::new($false));          if (-not $__kaku_ok -and $__kaku_rc -eq 0) {{ $__kaku_rc = 1 }};          exit $__kaku_rc",
        command, path
    )
}

// ─── Background process registry ─────────────────────────────────────────────

struct BgProcess {
    child: std::process::Child,
    output: Arc<Mutex<String>>,
}

impl Drop for BgProcess {
    fn drop(&mut self) {
        kill_process_group(&self.child);
        let _ = self.child.wait();
    }
}

static BG_PROCS: OnceLock<Mutex<HashMap<u32, BgProcess>>> = OnceLock::new();

fn bg_registry() -> &'static Mutex<HashMap<u32, BgProcess>> {
    BG_PROCS.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Spawn a reader thread that drains `reader` into `buf`, up to `cap` bytes
/// total (shared across sibling threads via `bytes_total`).
pub(super) fn pump_reader_capped<R: Read + Send + 'static>(
    reader: R,
    buf: Arc<Mutex<String>>,
    bytes_total: Arc<AtomicUsize>,
    cap: usize,
) -> std::thread::JoinHandle<()> {
    crate::thread_util::spawn_with_pool(move || {
        let mut r = reader;
        let mut chunk = [0u8; 8192];
        loop {
            match r.read(&mut chunk) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    let prev = bytes_total.fetch_add(n, Ordering::Relaxed);
                    if prev < cap {
                        if let Ok(mut g) = buf.lock() {
                            let room = cap.saturating_sub(g.len());
                            if room > 0 {
                                let to_write = n.min(room);
                                g.push_str(&String::from_utf8_lossy(&chunk[..to_write]));
                            }
                        }
                    }
                }
            }
        }
    })
}

pub(super) fn exec_shell_exec(
    args: &serde_json::Value,
    cwd: &mut String,
    cap: usize,
    cancel: &Arc<AtomicBool>,
) -> Result<String> {
    let command = args["command"].as_str().context("missing command")?;
    let exec_cwd = args["cwd"]
        .as_str()
        .map(|p| resolve(p, cwd))
        .transpose()?
        .unwrap_or_else(|| PathBuf::from(cwd.as_str()));

    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    let cwd_tmp_path =
        std::env::temp_dir().join(format!("kaku_cwd_{}_{}.txt", std::process::id(), ts));
    // create_new + mode 0o600 ensures we own the file exclusively before the shell writes to it.
    // Propagate on failure: an EEXIST or symlink collision here would allow the shell redirection
    // to follow a pre-placed symlink, turning this into a write-anywhere primitive.
    let mut options = std::fs::OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    options.mode(0o600);
    options
        .open(&cwd_tmp_path)
        .with_context(|| format!("could not create temp cwd file {}", cwd_tmp_path.display()))?;
    let shell = default_shell();
    let wrapped = shell_exec_wrapper(command, &cwd_tmp_path, &shell);
    let streaming_cap = cap.saturating_sub(512);

    let mut cmd = shell_command(&shell, &wrapped);
    configure_process(&mut cmd);
    let mut child = cmd
        .current_dir(&exec_cwd)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .with_context(|| format!("shell exec failed ({})", shell))?;

    let bytes_total = Arc::new(AtomicUsize::new(0));
    let stdout_buf = Arc::new(Mutex::new(String::new()));
    let stderr_buf = Arc::new(Mutex::new(String::new()));

    let h1 = child
        .stdout
        .take()
        .map(|s| pump_reader_capped(s, stdout_buf.clone(), bytes_total.clone(), streaming_cap));
    let h2 = child
        .stderr
        .take()
        .map(|s| pump_reader_capped(s, stderr_buf.clone(), bytes_total.clone(), streaming_cap));

    let start = Instant::now();
    let timeout = Duration::from_secs(SHELL_EXEC_TIMEOUT_SECS);
    let mut canceled = false;
    let mut timed_out = false;
    let mut overflowed = false;
    loop {
        if cancel.load(Ordering::Relaxed) {
            kill_process_group(&child);
            canceled = true;
            break;
        }
        if start.elapsed() >= timeout {
            kill_process_group(&child);
            timed_out = true;
            break;
        }
        if !overflowed && bytes_total.load(Ordering::Relaxed) >= streaming_cap {
            overflowed = true;
        }
        if let Ok(Some(_)) = child.try_wait() {
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    let status = child.wait().ok();
    if let Some(h) = h1 {
        let _ = h.join();
    }
    if let Some(h) = h2 {
        let _ = h.join();
    }

    let stdout_raw = stdout_buf.lock().map(|g| g.clone()).unwrap_or_default();
    if let Ok(new_dir) = std::fs::read_to_string(&cwd_tmp_path) {
        let new_dir = new_dir.trim().to_string();
        if !new_dir.is_empty() {
            *cwd = new_dir;
        }
    }
    let _ = std::fs::remove_file(&cwd_tmp_path);

    let mut stdout_lines: Vec<&str> = stdout_raw.lines().collect();
    stdout_lines.retain(|l| !l.starts_with("__KAKU_CWD__:"));
    let mut out = stdout_lines.join("\n");
    if stdout_raw.ends_with('\n') && !out.ends_with('\n') {
        out.push('\n');
    }
    let stderr_str = stderr_buf.lock().map(|g| g.clone()).unwrap_or_default();
    if !stderr_str.is_empty() {
        if !out.is_empty() {
            out.push('\n');
        }
        out.push_str("[stderr] ");
        out.push_str(&stderr_str);
    }
    if overflowed {
        let total = bytes_total.load(Ordering::Relaxed);
        out.push_str(&format!(
            "\n[truncated: first ~{} bytes shown ({} total). \
             For large output, use shell_bg + shell_poll to avoid waiting.]",
            streaming_cap, total
        ));
    }
    if canceled {
        out.push_str("\n[canceled by user before completion]");
    }
    if timed_out {
        out.push_str(&format!(
            "\n[killed: exceeded {}s timeout. For long-running commands \
             use shell_bg + shell_poll; for searching code use grep_search.]",
            SHELL_EXEC_TIMEOUT_SECS
        ));
    }
    if let Some(s) = status {
        if !s.success() && !canceled && !timed_out {
            let code = s.code().unwrap_or(-1);
            out.push_str(&format!("\n[exit {}]", code));
        }
    }
    if out.trim().is_empty() {
        Ok("(no output)".into())
    } else {
        Ok(out)
    }
}

// Signature matches the rest of the tool dispatch table in mod.rs which all
// take `&mut String` even when individual tools only read; keeping it
// uniform makes the dispatcher symmetric.
#[allow(clippy::ptr_arg)]
pub(super) fn exec_shell_bg(args: &serde_json::Value, cwd: &mut String) -> Result<String> {
    let command = args["command"].as_str().context("missing command")?;
    let exec_cwd = args["cwd"]
        .as_str()
        .map(|p| resolve(p, cwd))
        .transpose()?
        .unwrap_or_else(|| PathBuf::from(cwd.as_str()));
    let shell = default_shell();
    let mut cmd = shell_command(&shell, command);
    configure_process(&mut cmd);
    let mut child = cmd
        .current_dir(&exec_cwd)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .with_context(|| format!("failed to spawn background command: {}", command))?;
    let pid = child.id();
    let output = Arc::new(Mutex::new(String::new()));
    let bg_cap = super::registry::budget_for("shell_bg", "default");
    let bg_bytes = Arc::new(AtomicUsize::new(0));
    if let Some(stdout) = child.stdout.take() {
        let _ = pump_reader_capped(stdout, output.clone(), bg_bytes.clone(), bg_cap);
    }
    if let Some(stderr) = child.stderr.take() {
        let _ = pump_reader_capped(stderr, output.clone(), bg_bytes.clone(), bg_cap);
    }
    bg_registry()
        .lock()
        .unwrap_or_else(|e| e.into_inner())
        .insert(pid, BgProcess { child, output });
    Ok(format!(
        "Background process started (pid {}). Use shell_poll to check status.",
        pid
    ))
}

pub(super) fn exec_shell_poll(
    args: &serde_json::Value,
    cancel: &Arc<AtomicBool>,
) -> Result<String> {
    let pid = args["pid"].as_u64().context("missing pid")? as u32;
    let timeout_secs = args["timeout_secs"].as_u64().unwrap_or(0);

    let (snapshot, status_opt) = {
        let mut registry = bg_registry().lock().unwrap_or_else(|e| e.into_inner());
        let proc = registry
            .get_mut(&pid)
            .ok_or_else(|| anyhow::anyhow!("no background process with pid {}", pid))?;
        let snap = proc
            .output
            .lock()
            .ok()
            .map(|g| g.clone())
            .unwrap_or_default();
        let status = proc.child.try_wait().ok().flatten();
        (snap, status)
    };

    let final_status = if timeout_secs == 0 || status_opt.is_some() {
        status_opt
    } else {
        let deadline = Instant::now() + Duration::from_secs(timeout_secs);
        loop {
            std::thread::sleep(Duration::from_millis(200));
            if cancel.load(Ordering::Relaxed) || Instant::now() >= deadline {
                break None;
            }
            let mut registry = bg_registry().lock().unwrap_or_else(|e| e.into_inner());
            if let Some(proc) = registry.get_mut(&pid) {
                if let Ok(Some(s)) = proc.child.try_wait() {
                    break Some(s);
                }
            } else {
                break None;
            }
        }
    };

    let final_snapshot = if final_status.is_some() {
        let mut registry = bg_registry().lock().unwrap_or_else(|e| e.into_inner());
        let snap = registry
            .get(&pid)
            .and_then(|p| p.output.lock().ok().map(|g| g.clone()))
            .unwrap_or(snapshot);
        registry.remove(&pid);
        snap
    } else {
        snapshot
    };

    let (done_str, exit_str): (String, String) = match final_status {
        Some(s) => {
            let code = s.code().unwrap_or(-1);
            ("done".into(), format!("[exit {}]", code))
        }
        None => ("running".into(), String::new()),
    };

    if final_snapshot.is_empty() {
        Ok(format!("pid {}: {} {}", pid, done_str, exit_str))
    } else {
        Ok(format!(
            "pid {}: {} {}\n{}",
            pid, done_str, exit_str, final_snapshot
        ))
    }
}

#[cfg(all(test, unix))]
mod tests {
    use super::shell_exec_wrapper;
    use std::path::Path;

    #[test]
    fn shell_command_preserves_exit_status_and_cwd() {
        let path = std::env::temp_dir().join(format!("kaku-shell-test-{}.txt", std::process::id()));
        let file = std::fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&path)
            .unwrap();
        drop(file);
        let wrapped = shell_exec_wrapper("cd /; false", &path, "/bin/bash");
        let status = super::shell_command("/bin/bash", &wrapped)
            .status()
            .unwrap();
        let cwd = std::fs::read_to_string(&path).unwrap();
        std::fs::remove_file(path).unwrap();
        assert_eq!(status.code(), Some(1));
        assert_eq!(cwd, "/");
    }

    #[test]
    fn shell_exec_wrapper_uses_fish_syntax() {
        let wrapped =
            shell_exec_wrapper("false", Path::new("/tmp/kaku-cwd"), "/usr/local/bin/fish");

        assert_eq!(
            wrapped,
            "false; set __kaku_rc $status; printf '%s' (pwd) > /tmp/kaku-cwd; exit $__kaku_rc"
        );
    }

    #[test]
    fn shell_exec_wrapper_keeps_posix_syntax_for_zsh_and_bash() {
        for shell in ["/bin/bash", "/bin/zsh"] {
            let wrapped = shell_exec_wrapper("false", Path::new("/tmp/kaku-cwd"), shell);

            assert_eq!(
                wrapped,
                "false; __kaku_rc=$?; printf '%s' \"$(pwd)\" > /tmp/kaku-cwd; exit $__kaku_rc"
            );
        }
    }
}

#[cfg(all(test, windows))]
mod windows_tests {
    use super::*;
    #[test]
    fn powershell_reports_exit_status_and_changed_directory() {
        let dir = tempfile::tempdir().unwrap();
        let cwd_path = dir.path().join("cwd's file.txt");
        std::fs::write(&cwd_path, "").unwrap();
        let command = format!(
            "Set-Location '{}'; cmd /c exit 7",
            dir.path().to_string_lossy().replace("\u{27}", "''")
        );
        let wrapped = shell_exec_wrapper(&command, &cwd_path, &default_shell());
        let status = shell_command(&default_shell(), &wrapped).status().unwrap();
        assert_eq!(status.code(), Some(7));
        let cwd = std::fs::read_to_string(&cwd_path).unwrap();
        assert_eq!(Path::new(cwd.trim()), dir.path());
    }
}
