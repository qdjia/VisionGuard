use std::{
    io::{Read, Write},
    net::{Shutdown, SocketAddr, TcpListener},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, MutexGuard,
    },
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

static TEST_LOCK: Mutex<()> = Mutex::new(());

fn serial_guard() -> MutexGuard<'static, ()> {
    TEST_LOCK
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

struct FakeRuntime {
    endpoint: String,
    stopped: Arc<AtomicBool>,
    worker: Option<JoinHandle<()>>,
}

impl FakeRuntime {
    fn start(ready_after: Duration) -> Self {
        Self::start_with_shutdown_behavior(ready_after, true)
    }

    fn start_ignoring_shutdown(ready_after: Duration) -> Self {
        Self::start_with_shutdown_behavior(ready_after, false)
    }

    fn start_with_shutdown_behavior(ready_after: Duration, graceful_shutdown: bool) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").expect("dynamic loopback port");
        listener
            .set_nonblocking(true)
            .expect("nonblocking listener");
        let address = listener.local_addr().expect("listener address");
        let endpoint = format!("http://{address}");
        let stopped = Arc::new(AtomicBool::new(false));
        let worker_stopped = Arc::clone(&stopped);
        let worker = thread::spawn(move || {
            let started = Instant::now();
            while !worker_stopped.load(Ordering::SeqCst) {
                match listener.accept() {
                    Ok((mut stream, _)) => {
                        stream
                            .set_nonblocking(false)
                            .expect("blocking client stream");
                        stream
                            .set_read_timeout(Some(Duration::from_secs(1)))
                            .expect("client read timeout");
                        let mut request = [0_u8; 2048];
                        let count = stream.read(&mut request).unwrap_or(0);
                        let request = String::from_utf8_lossy(&request[..count]);
                        let (status, body) = if request.starts_with("GET /health/live ") {
                            ("200 OK", r#"{"status":"ok"}"#)
                        } else if request.starts_with("GET /health/ready ") {
                            if started.elapsed() >= ready_after {
                                ("200 OK", r#"{"status":"ready","components":{}}"#)
                            } else {
                                ("503 Service Unavailable", r#"{"status":"starting"}"#)
                            }
                        } else if request.starts_with("POST /_runtime/shutdown ") {
                            if graceful_shutdown {
                                worker_stopped.store(true, Ordering::SeqCst);
                            }
                            ("200 OK", r#"{"status":"stopping"}"#)
                        } else {
                            ("404 Not Found", "{}")
                        };
                        let response = format!(
                            "HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
                            body.len()
                        );
                        stream
                            .write_all(response.as_bytes())
                            .expect("fake runtime response");
                        stream.flush().expect("flush fake runtime response");
                        let _ = stream.shutdown(Shutdown::Write);
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(10));
                    }
                    Err(_) => break,
                }
            }
        });
        Self {
            endpoint,
            stopped,
            worker: Some(worker),
        }
    }

    fn address(&self) -> SocketAddr {
        self.endpoint
            .trim_start_matches("http://")
            .parse()
            .expect("fake runtime endpoint")
    }

    fn force_stop(&self) {
        self.stopped.store(true, Ordering::SeqCst);
    }

    fn join(mut self) {
        if let Some(worker) = self.worker.take() {
            worker.join().expect("fake runtime worker");
        }
    }
}

fn request_succeeds(endpoint: &str, path: &str) -> bool {
    tauri::async_runtime::block_on(async {
        reqwest::get(format!("{endpoint}{path}"))
            .await
            .map(|response| response.status().is_success())
            .unwrap_or(false)
    })
}

fn wait_until_ready(endpoint: &str, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if request_succeeds(endpoint, "/health/ready") {
            return true;
        }
        thread::sleep(Duration::from_millis(10));
    }
    false
}

impl Drop for FakeRuntime {
    fn drop(&mut self) {
        self.stopped.store(true, Ordering::SeqCst);
        if let Some(worker) = self.worker.take() {
            worker.join().expect("fake runtime worker");
        }
    }
}

#[test]
fn fake_runtime_uses_dynamic_loopback_port_and_becomes_ready() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::from_millis(30));
    assert_eq!(fake.address().ip().to_string(), "127.0.0.1");
    assert_ne!(fake.address().port(), 0);
    tauri::async_runtime::block_on(async {
        assert!(reqwest::get(format!("{}/health/live", fake.endpoint))
            .await
            .expect("live response")
            .status()
            .is_success());
        thread::sleep(Duration::from_millis(100));
        assert!(reqwest::get(format!("{}/health/ready", fake.endpoint))
            .await
            .expect("ready response")
            .status()
            .is_success());
    });
}

#[test]
fn fake_runtime_spawn_exposes_live_probe() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::ZERO);
    assert!(request_succeeds(&fake.endpoint, "/health/live"));
}

#[test]
fn readiness_polling_waits_for_model_initialization() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::from_millis(40));
    assert!(wait_until_ready(&fake.endpoint, Duration::from_secs(1)));
}

#[test]
fn fake_runtime_supports_slow_ready_and_timeout_probe() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::from_secs(2));
    tauri::async_runtime::block_on(async {
        let response = reqwest::get(format!("{}/health/ready", fake.endpoint))
            .await
            .expect("starting response");
        assert_eq!(response.status(), reqwest::StatusCode::SERVICE_UNAVAILABLE);
    });
}

#[test]
fn readiness_polling_respects_startup_timeout() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::from_secs(2));
    assert!(!wait_until_ready(&fake.endpoint, Duration::from_millis(50)));
}

#[test]
fn stopped_runtime_is_detectable() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::ZERO);
    let address = fake.address();
    fake.force_stop();
    fake.join();
    assert!(std::net::TcpStream::connect_timeout(&address, Duration::from_millis(50)).is_err());
}

#[test]
fn runtime_can_restart_after_a_clean_stop() {
    let _guard = serial_guard();
    let first = FakeRuntime::start(Duration::ZERO);
    first.force_stop();
    first.join();
    let restarted = FakeRuntime::start(Duration::ZERO);
    assert!(request_succeeds(&restarted.endpoint, "/health/live"));
}

#[test]
fn injected_endpoint_targets_the_managed_runtime() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::ZERO);
    let injected_endpoint = fake.endpoint.clone();
    assert!(request_succeeds(&injected_endpoint, "/health/live"));
}

#[test]
fn force_stop_fallback_handles_ignored_shutdown() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start_ignoring_shutdown(Duration::ZERO);
    let address = fake.address();
    tauri::async_runtime::block_on(async {
        reqwest::Client::new()
            .post(format!("{}/_runtime/shutdown", fake.endpoint))
            .send()
            .await
            .expect("ignored shutdown response");
    });
    assert!(request_succeeds(&fake.endpoint, "/health/live"));
    fake.force_stop();
    fake.join();
    assert!(TcpListener::bind(address).is_ok());
}

#[test]
fn dropping_runtime_does_not_leave_an_orphan_listener() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::ZERO);
    let address = fake.address();
    drop(fake);
    assert!(TcpListener::bind(address).is_ok());
}

#[test]
fn fake_runtime_graceful_shutdown_leaves_no_listener() {
    let _guard = serial_guard();
    let fake = FakeRuntime::start(Duration::ZERO);
    let address = fake.address();
    tauri::async_runtime::block_on(async {
        reqwest::Client::new()
            .post(format!("{}/_runtime/shutdown", fake.endpoint))
            .send()
            .await
            .expect("shutdown response");
    });
    fake.join();
    assert!(
        TcpListener::bind(address).is_ok(),
        "listener should be released"
    );
}
