use serde::{Deserialize, Serialize};

pub type TabId = u32;
pub type WindowId = u32;

#[derive(Debug, Serialize, Deserialize)]
pub struct TabEvent {
    pub action: String,
    pub key: Option<String>,

    #[serde(flatten)]
    pub tab_info: TabInfo,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TabInfo {
    pub tab_id: TabId,
    #[serde(flatten)]
    pub attributes: TabAttributes,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TabAttributes {
    pub title: Option<String>,
    pub url: Option<String>,
    pub window_id: Option<WindowId>,
}

pub type DBusTabInfo = (TabId, String, String, WindowId);
pub type DBusTabInfoList = Vec<DBusTabInfo>;

impl TabAttributes {
    pub fn merge(&mut self, other: &TabAttributes) {
        if self.title.is_none() {
            self.title = other.title.as_ref().map(|v| v.to_string());
        }
        if self.url.is_none() {
            self.url = other.url.as_ref().map(|v| v.to_string());
        }
        if self.window_id.is_none() {
            self.window_id = other.window_id;
        }
    }
}

pub fn unpack_tabs(values: &[(TabId, &TabAttributes)]) -> DBusTabInfoList {
    values.iter().map(|v| tab_to_tuple(v)).collect()
}

// TODO: use &TabInfo instead of tuple?
pub fn tab_to_tuple(v: &(TabId, &TabAttributes)) -> DBusTabInfo {
    let attributes = v.1;
    let title = attributes
        .title
        .as_ref()
        .cloned()
        .unwrap_or_else(|| "".to_string());
    let url = attributes
        .url
        .as_ref()
        .cloned()
        .unwrap_or_else(|| "".to_string());
    let window_id = attributes.window_id.unwrap_or(0);
    (v.0, title, url, window_id)
}

pub fn tuple_to_tab(source: &DBusTabInfo) -> TabInfo {
    let tab_id = source.0;
    let title = get_option_string(&source.1);
    let url = get_option_string(&source.2);
    let window_id = get_option_u32(&source.3);
    TabInfo {
        tab_id,
        attributes: TabAttributes {
            title,
            url,
            window_id,
        },
    }
}

fn get_option_string(source: &str) -> Option<String> {
    if source.is_empty() {
        None
    } else {
        Some(source.to_string())
    }
}

fn get_option_u32(source: &u32) -> Option<u32> {
    if *source == 0 {
        None
    } else {
        Some(*source)
    }
}

pub fn none_to_empty(value: Option<&str>) -> &str {
    if let Some(value) = value {
        value
    } else {
        ""
    }
}

// Can't solve the "" vs "".to_string() issue with AsRef<str>
pub fn none_to_empty_string(value: Option<String>) -> String {
    if let Some(value) = value {
        value
    } else {
        "".to_string()
    }
}

pub fn empty_to_none(value: String) -> Option<String> {
    if value.is_empty() {
        None
    } else {
        Some(value)
    }
}
