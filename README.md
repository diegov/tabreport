# TabReport 

Lightweight command-line Firefox tab listing and activation for Linux, using DBus.

There is at least one better solution for this out there, but it's not verified by Mozilla, and it's not popular enough to trust the "given enough eyeballs..." principle.
Since I only use Linux, I prefer to provide the tab info via DBus rather than net sockets. I also wanted something that played along with [i3](https://i3wm.org/) and [Sway](https://swaywm.org/) without changing my [focus\_on\_window\_activation](https://i3wm.org/docs/userguide.html#focus_on_window_activation) settings.

So I hacked just enough code to solve my problem.

If you need a real tab switching extension and not just a personal hack like this, the most popular (the only?) one is [Brotab](https://github.com/balta2ar/brotab).

## Installation

Building the extension requires the following

- Rust and Cargo (tested with version 1.52, older versions might work as well)
- DBus development headers (eg. package `libdbus-1-dev` on Debian and derivatives)
- NodeJS and NPM
- Optional: `strip` to reduce binary size (eg. package `binutils` on Debian and derivatives)

### Steps

- Clone this repo
- Audit the code thoroughly (it's small)
- Set `xpinstall.signatures.required` to false in Firefox's `about:config`
- [`./build.sh`](build.sh)
- [`./install_native.sh`](install_native.sh)
- `cd extension`
- `firefox tabreport-0.1.0.xpi`

At this point Firefox should prompt you to install the extension.

Note the stable Firefox builds downloaded from mozilla.org don't support setting `xpinstall.signatures.required` to false. 
Ubuntu and Debian's packages do, and Developer and Nighly editions from mozilla.org do as well.

[`install_native.sh`](install_native.sh) assumes you have a `~/.local/bin` directory, and that it's in the `PATH` used in your shell. If that's not the case modify it as needed.

If you installed Firefox via Flatpak or use other sandboxing solutions you'll probably need to tweak all the paths and set up additional permissions.

## Usage

The extension registers a DBus service called `net.diegoveralli.tabreport` that does all the work, but there's a small `tabreport` CLI client that can be used to interact with it:

- `tabreport`

Show a list of open tabs in json format. To make it more readable, you can pipe it to [jq](https://github.com/stedolan/jq): `tabreport | jq`.
The tab list is sorted by most recently updated / activated. 

- `tabreport TAB_ID`

Activate the tab with the given ID, and focus its window.

- `tabreport TAB_ID --mark TITLE_PREFACE`

Activate the tab with the given ID, focus its window, and set its `titlePreface` (see the [`windows.update` documentation](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/windows/update)).

- `tabreport TAB_ID --reset`

Clear the tab's window's `titlePreface`.

Eg.:

```shell
$ tabreport | jq
[
  {
    "tab_id": 2,
    "title": "Download the Firefox Browser in English (US) and more than 90 other languages",
    "url": "https://www.mozilla.org/en-US/firefox/all/#product-desktop-release",
    "window_id": 1
  },
  {
    "tab_id": 1,
    "title": "New Tab",
    "url": "about:blank",
    "window_id": 1
  },
  {
    "tab_id": 3,
    "title": "Matrix.org",
    "url": "https://matrix.org/",
    "window_id": 2
  }
]
$ tabreport 2 # Activate tab 2, and focus its window
```

### The activation hack to avoid [focus\_on\_window\_activation](https://i3wm.org/docs/userguide.html#focus_on_window_activation)

Since I couldn't find a way to get a reference to the native window handle in the WebExtension API, the extension supports setting the `titlePreface` (see the [`windows.update` documentation](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/windows/update)) to identify the window. The `--mark PREFACE` and `--reset` switches can be used for this.

This works in i3 and sway, with the same syntax.

Eg.:

```shell
$ tabreport | jq
[
  {
    "tab_id": 2,
    "title": "Download the Firefox Browser in English (US) and more than 90 other languages",
    "url": "https://www.mozilla.org/en-US/firefox/all/#product-desktop-release",
    "window_id": 1
  },
  {
    "tab_id": 1,
    "title": "New Tab",
    "url": "about:blank",
    "window_id": 1
  },
  {
    "tab_id": 3,
    "title": "Matrix.org",
    "url": "https://matrix.org/",
    "window_id": 2
  }
]
$ tabreport 3 --mark someuniqueid # Activates tab 3 and its window, and also sets "someuniqueid" as the `titlePreface`
$ i3-msg '[title="someuniqueid*"] focus' # Tells i3 to focus the window whose title starts with the unique id we set
[{"success":true}]
$ tabreport 3 --reset # Clears the window's `titlePreface`
```

The DBus service waits for the JS extension to let it know it's done updating the tab and window, so the DBus response (and consequently the `tabreport TAB_ID` execution) _should_ only return once the window title change is visible to the window manager. 

This means in theory we don't need to wait between the `tabreport TAB_ID...` invocation and the `i3-msg` or `swaymsg` invocation. But I suspect the `window.update` promise in the JS code doesn't represent the entirety of the asynchronicity going on when updating a window through the browser / Xorg / i3 / sway, so it's possible this might require some sleep time. In my tests it always works without it.

See [`examples/dmenu_test`](examples/dmenu_test) for an full example script using `dmenu` or `bemenu` to select the tab.
 
## License

[GPLv3](LICENSE)
