use dbus::blocking::Connection;
use std::env;
use std::time::Duration;
use tabreport_common::*;

fn activate(
    tab_id: u32,
    window_preface: Option<&str>,
) -> Result<String, Box<dyn std::error::Error>> {
    run_dbus_action(|proxy| {
        let args: (u32, &str) = (tab_id, none_to_empty(window_preface));
        let (msg,): (String,) =
            proxy.method_call("net.diegoveralli.tabreport", "Activate", args)?;

        Ok(msg)
    })
}

fn reset(tab_id: u32) -> Result<String, Box<dyn std::error::Error>> {
    run_dbus_action(|proxy| {
        let args: (u32,) = (tab_id,);
        let (msg,): (String,) = proxy.method_call("net.diegoveralli.tabreport", "Reset", args)?;
        Ok(msg)
    })
}

fn run_dbus_action<F, R>(action: F) -> Result<R, Box<dyn std::error::Error>>
where
    F: Fn(&dbus::blocking::Proxy<&Connection>) -> Result<R, Box<dyn std::error::Error>>,
{
    let conn = Connection::new_session()?;
    let proxy = conn.with_proxy(
        "net.diegoveralli.tabreport",
        "/net/diegoveralli/tabreport",
        Duration::from_millis(2000),
    );

    action(&proxy)
}

fn get_list() -> Result<Vec<TabInfo>, Box<dyn std::error::Error>> {
    let conn = Connection::new_session()?;

    let proxy = conn.with_proxy(
        "net.diegoveralli.tabreport",
        "/net/diegoveralli/tabreport",
        Duration::from_millis(5000),
    );

    let args: (&str,) = ("dummy",);

    let result: Result<(DBusTabInfoList,), dbus::Error> =
        proxy.method_call("net.diegoveralli.tabreport", "TabReport", args);

    match result {
        Ok((tab_list,)) => {
            let result = tab_list.iter().map(|v| tuple_to_tab(v)).collect();
            Ok(result)
        }
        Err(e) => {
            if let Some("org.freedesktop.DBus.Error.ServiceUnknown") = e.name() {
                // This is probably OK, firefox might not be running
                eprintln!("WARN: DBus service net.diegoveralli.tabreport not found");
                Ok(vec![])
            } else {
                Err(e.into())
            }
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let mut tab_id: Option<u32> = None;
    let mut title_preface: Option<&str> = None;
    let mut getting_window_title = false;
    let mut is_reset = false;

    for arg in &args[1..] {
        if getting_window_title {
            title_preface = Some(arg);
            getting_window_title = false;
        } else if !arg.starts_with("--") {
            tab_id = Some(arg.parse()?);
        } else if arg == "--mark" {
            getting_window_title = true;
        } else if arg == "--reset" {
            is_reset = true;
        }
    }
    if let Some(tab_id) = tab_id {
        if is_reset {
            reset(tab_id)?;
        } else {
            activate(tab_id, title_preface)?;
        }
    } else {
        let tabs = get_list()?;
        println!("{}", serde_json::to_string(&tabs)?);
    }

    Ok(())
}
