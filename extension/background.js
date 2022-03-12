function initialise() {
  var port = browser.runtime.connectNative("net.diegoveralli.tabreport");

  port.onMessage.addListener(async (request) => {
    let error = null;

    let preface = request['window_title_preface'];
    let seqNum = request['sequence_number'];

    let syncKey = '';
    if (preface) {
      syncKey = preface;
    }

    let id = request['tab_id'];

    try {
      let tab = await browser.tabs.get(id);

      if (request['action'] == 'activate') {
        await browser.tabs.update(id, { active: true });
        // TODO: Setting focused and drawAttention should be optional, in case we want to 
        // fully handle window and workspace switching on the window manager side
        // TODO: In theory drawAttention does nothing on a window that's already focused,
        // so it's probably useless here.
        var attributes = { focused: true, drawAttention: true };

        if (preface) {
          attributes['titlePreface'] = preface;
        }

        await browser.windows.update(tab.windowId, attributes);
      } else if (request['action'] == 'reset') {
        await browser.windows.update(tab.windowId, {titlePreface: ""});
      }
    } catch (e) {
      error = e;
    }

    // Send sync request to host, so that they know we're done with the update.
    // This is important when the client is hacking the window title to be able to locate
    // the window later: it will wait until we're done here, then go through the available
    // windows to find the one whose workspace it needs to switch to.
    // This is a window title update, something assumed to be mostly cosmetic, that
    // goes through browser -> (xorg | wayland compositor), so assuming this change
    // is immediately visible to clients after the `window.update` promise resolves is
    // very optimistic. In practice it always works, but it's hard to know whether
    // that's guaranteed or just processed faster than however long it takes for the
    // host process to resume. There's a lot of xorg / i3 / sway / firefox code to go
    // through to understand what we can expect here because information on sequential
    // consistency is not part of the docs.

    let message = {'action': 'sync', 'key': syncKey, 'tab_id': id, 'sequence_number': seqNum};
    if (error != null) {
      message['error'] = JSON.stringify(error);
    }
    
    port.postMessage(message);
  });

  function sendUpdate(tabId, changes, force) {
    var msg = {};
    for (let change of changes) {
      if (change.title) {
        msg['title'] = change.title;
      }
      if (change.url) {
        msg['url'] = change.url;
      }
      if (change.windowId) {
        msg['window_id'] = change.windowId;
      }
    }

    if (Object.keys(msg) || force) {
      msg['action'] = 'update';
      msg['tab_id'] = tabId;
      port.postMessage(msg);  
    };
  }

  function handleUpdated(tabId, changeInfo, _tabInfo) {
    sendUpdate(tabId, [changeInfo]);
  }

  function handleActivated(info) {
    sendUpdate(info.tabId, [info], true);
  }

  function handleRemoved(tabId, _info) {
    port.postMessage({
      action: 'remove',
      tab_id: tabId
    });
  }

  async function handleWindowFocus(windowId) {
    if (windowId != browser.windows.WINDOW_ID_NONE) {
      let window = await browser.windows.get(windowId);
      let tabs = await browser.tabs.query({windowId: window.id, active: true});
      for (let tab of tabs) {
        if (tab.id) {
          sendUpdate(tab.id, [tab], true);
        }
      }
    }
  }

  browser.tabs.onUpdated.addListener(handleUpdated);
  browser.tabs.onActivated.addListener(handleActivated);
  browser.tabs.onRemoved.addListener(handleRemoved);
  browser.windows.onFocusChanged.addListener(handleWindowFocus);

  browser.tabs.query({}).then((tabs) => {
    for (let tab of tabs) {
      if (tab.id) {
        sendUpdate(tab.id, [tab]);
      } else {
        console.error('No tab id: ' + JSON.stringify(tab));
      }
    }
  });
}

browser.runtime.onStartup.addListener(initialise);
browser.runtime.onInstalled.addListener(initialise);
