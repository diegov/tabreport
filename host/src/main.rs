extern crate serde;
extern crate serde_derive;

use byteorder::{NativeEndian, ReadBytesExt, WriteBytesExt};
use dbus::blocking::Connection;
use dbus::channel::MatchingReceiver;
use dbus_crossroads::{Context, Crossroads};
use serde::Serialize;
use std::collections::HashMap;
use std::error::Error;
use std::io::ErrorKind;
use std::io::Write;
use std::io::{self, Cursor, Read};
use std::str;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;
use std::time::SystemTime;
use std::time::{Duration, Instant};
use tabreport_common::empty_to_none;
use tabreport_common::{unpack_tabs, TabAttributes, TabEvent, TabId, WindowId};

type TabData = HashMap<TabId, (SystemTime, TabAttributes)>;

type SignalData = (Mutex<HashMap<u64, Option<String>>>, Condvar);

type TabReportContext = (Arc<Mutex<TabData>>, Arc<SignalData>, Arc<AtomicU64>);

trait KeySignal {
    fn sync_complete(&self, sequence_number: u64, error: Option<String>);
    fn wait_for_sync(&self, sequence_number: u64) -> Result<(), dbus::MethodErr>;
}

impl KeySignal for SignalData {
    fn sync_complete(&self, sequence_number: u64, error: Option<String>) {
        let (lock, cvar) = &*self;
        let mut started = lock.lock().unwrap();
        started.insert(sequence_number, error);
        cvar.notify_all();
    }

    fn wait_for_sync(&self, sequence_number: u64) -> Result<(), dbus::MethodErr> {
        let (lock, cvar) = &*self;
        let mut started = lock.lock().map_err(|e| dbus::MethodErr::failed(&e))?;

        log(format!("Waiting for {:?}", &sequence_number));

        let start = Instant::now();

        while !started.contains_key(&sequence_number) {
            // TODO: dbus::blocking is showing its limitations here, the service
            // won't respond to other queries while this is waiting, which is
            // very noticeable when there's an error and we don't get a sync
            // message back. We need to use dbus-tokio.
            if start.elapsed().as_millis() > 5000 {
                return Err(dbus::MethodErr::failed(
                    "More than 5 seconds without response from Firefox extension",
                ));
            }
            let new_value = cvar
                .wait_timeout(started, Duration::from_secs(3))
                .map_err(|e| dbus::MethodErr::failed(&e))?;
            started = new_value.0;
        }

        let error = started.remove(&sequence_number);

        log(format!("Synchronized {:?}", &sequence_number));

        if let Some(Some(error)) = error {
            return Err(dbus::MethodErr::failed(&error));
        }

        Ok(())
    }
}

#[derive(Debug, Serialize)]
struct Command {
    action: String,
    tab_id: TabId,
    window_id: Option<WindowId>,
    window_title_preface: Option<String>,
    sequence_number: u64,
}

fn get_sequence_number(source: &Arc<AtomicU64>) -> u64 {
    // % for the max integer we can use in JS with full precision.
    source.fetch_add(1, Ordering::SeqCst) % 999999999999999u64
}

fn serve(do_run: Arc<AtomicBool>, data: TabReportContext) -> Result<(), Box<dyn Error>> {
    let c = Connection::new_session()?;
    c.request_name("net.diegoveralli.tabreport", false, true, false)?;

    let mut cr = Crossroads::new();

    let iface_token = cr.register("net.diegoveralli.tabreport", |b| {
        b.method(
            "TabReport",
            (),
            ("reply",),
            |_ctx: &mut Context, (tab_data, _, _): &mut TabReportContext, (): ()| {
                let current = tab_data.lock().unwrap();
                let result = get_sorted_list(&current);
                Ok((unpack_tabs(&result),))
            },
        );

        b.method(
            "Activate",
            ("tab_id", "window_title_preface"),
            ("reply",),
            move |_ctx: &mut Context,
                  (_, signal_data, seq_nums): &mut TabReportContext,
                  (tab_id, title_preface): (TabId, String)| {
                let preface = empty_to_none(title_preface);

                let sequence_number = get_sequence_number(seq_nums);

                let command = Command {
                    action: "activate".to_string(),
                    tab_id,
                    window_id: None::<WindowId>,
                    window_title_preface: preface,
                    sequence_number,
                };

                let body =
                    serde_json::to_string(&command).map_err(|e| dbus::MethodErr::failed(&e))?;

                let reply = write_to_stdout(&body)?;

                signal_data.wait_for_sync(sequence_number)?;

                Ok(reply)
            },
        );

        b.method(
            "Reset",
            ("tab_id",),
            ("reply",),
            |_ctx: &mut Context,
             (_, signal_data, seq_nums): &mut TabReportContext,
             (tab_id,): (TabId,)| {
                let sequence_number = get_sequence_number(seq_nums);

                let command = Command {
                    action: "reset".to_string(),
                    tab_id,
                    window_id: None::<WindowId>,
                    window_title_preface: None::<String>,
                    sequence_number,
                };

                let body =
                    serde_json::to_string(&command).map_err(|e| dbus::MethodErr::failed(&e))?;

                let reply = write_to_stdout(&body)?;

                signal_data.wait_for_sync(sequence_number)?;

                Ok(reply)
            },
        );
    });

    cr.insert("/net/diegoveralli/tabreport", &[iface_token], data);

    let id = c.start_receive(
        dbus::message::MatchRule::new_method_call(),
        Box::new(move |msg, conn| {
            match cr.handle_message(msg, conn) {
                Ok(()) => (),
                Err(()) => log("Failed to handle DBus message"),
            }
            true
        }),
    );

    while do_run.load(Ordering::SeqCst) {
        c.process(std::time::Duration::from_millis(1000))?;
    }

    log("Stopping receive");

    c.stop_receive(id);

    log("Exiting server loop");

    Ok(())
}

fn write_to_stdout(body: &str) -> Result<(String,), dbus::MethodErr> {
    let bytes = body.as_bytes();
    let mut stdout = io::stdout();
    stdout
        .write_u32::<NativeEndian>(bytes.len() as u32)
        .map_err(|e| dbus::MethodErr::failed(&e))?;

    stdout
        .write_all(bytes)
        .map_err(|e| dbus::MethodErr::failed(&e))?;

    stdout.flush().map_err(|e| dbus::MethodErr::failed(&e))?;

    Ok(("done".to_string(),))
}

fn get_sorted_list<'a>(
    map: &'a HashMap<TabId, (SystemTime, TabAttributes)>,
) -> Vec<(TabId, &'a TabAttributes)> {
    let mut result: Vec<(&SystemTime, (TabId, &'a TabAttributes))> = Vec::with_capacity(map.len());

    for (key, (ts, value)) in map {
        result.push((ts, (*key, value)));
    }

    result.sort_by(|a, b| b.0.cmp(a.0));

    result.into_iter().map(|v| v.1).collect()
}

fn log<S>(_msg: S)
where
    S: AsRef<str>,
{
    // use std::fs::OpenOptions;
    // use std::io::prelude::*;
    // let mut file = OpenOptions::new()
    //     .write(true)
    //     .create(true)
    //     .append(true)
    //     .open("/tmp/tabreport.log")
    //     .unwrap();

    // if let Err(e) = writeln!(file, "{}", msg.as_ref()) {
    //     eprintln!("Couldn't write to file: {}", e);
    // }
}

fn main() -> io::Result<()> {
    log("Starting tabreport..");

    let do_run = Arc::new(AtomicBool::new(true));

    let do_run_store = do_run.clone();
    ctrlc::set_handler(move || {
        log("Exiting...");
        do_run_store.store(false, Ordering::SeqCst);
    })
    .expect("Error setting Ctrl-C handler");

    let tab_data = Arc::new(Mutex::new(TabData::new()));
    let server_tab_data = Arc::clone(&tab_data);

    let signal_data = Arc::new((Mutex::new(HashMap::new()), Condvar::new()));
    let server_signal_data = Arc::clone(&signal_data);

    let server_do_run = do_run.clone();
    let dbus_thread = thread::spawn(|| {
        serve(
            server_do_run,
            (
                server_tab_data,
                server_signal_data,
                Arc::new(AtomicU64::new(0)),
            ),
        )
        .expect("Error running dbus service");
    });

    let mut stdin = io::stdin();

    while do_run.load(Ordering::SeqCst) {
        let event = match read_tab_info(&mut stdin) {
            Ok(tab_info) => tab_info,
            Err(error) => {
                if error.kind() == ErrorKind::UnexpectedEof {
                    do_run.store(false, Ordering::SeqCst);
                    break;
                } else {
                    return Err(error);
                }
            }
        };

        if event.action == "remove" {
            let mut data = tab_data.lock().unwrap();
            if data.remove(&event.tab_info.tab_id).is_none() {
                log(format!("No entry with id {} found", &event.tab_info.tab_id));
            }
        } else if event.action == "sync" {
            log(format!("Received sync for {:?}", event.sequence_number));
            signal_data.sync_complete(event.sequence_number.unwrap_or(0u64), event.error);
        } else {
            let mut data = tab_data.lock().unwrap();
            let mut attributes = event.tab_info.attributes;
            let curr_time = SystemTime::now();
            if let Some(existing) = data.get_mut(&event.tab_info.tab_id) {
                attributes.merge(&existing.1);
                *existing = (curr_time, attributes);
            } else {
                data.insert(event.tab_info.tab_id, (curr_time, attributes));
            }
        }
    }

    dbus_thread.join().unwrap();

    Ok(())
}

fn read_tab_info(stdin: &mut io::Stdin) -> io::Result<TabEvent> {
    let mut prefix = vec![0u8; 4];
    // log("About to read prefix");
    stdin.read_exact(&mut prefix)?;

    // log("Read 4 bytes of prefix");

    let mut reader = Cursor::new(prefix);

    let msg_len = reader.read_u32::<NativeEndian>()?;

    // log(format!("Decoded message length: {}", msg_len));

    let mut data = vec![0u8; msg_len as usize];
    stdin.read_exact(&mut data)?;

    // log("Read the data, decoding utf-8..");
    let msg_str = str::from_utf8(&data).map_err(|e| io::Error::new(ErrorKind::InvalidInput, e))?;

    log(msg_str);

    let tab_event_result = serde_json::from_str::<TabEvent>(msg_str);

    match tab_event_result {
        Err(what) => {
            log(what.to_string());
            std::panic::panic_any(what)
        }
        Ok(event) => Ok(event),
    }
}
