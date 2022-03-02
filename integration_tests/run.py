#!/usr/bin/env python3

import sys
import os
import os.path
import subprocess
import time
import json
import requests

from marionette_driver.marionette import Marionette
from marionette_driver.addons import Addons
from test_server import TestServer


ff_version = sys.argv[1]
extension_path = os.path.realpath(sys.argv[2])

cache_dir = os.environ.get("FF_CACHE_DIR") or os.path.join(
    os.path.expanduser("~"), ".cache", "addon_testing"
)


install_dir = os.path.join(cache_dir, f"ff-{ff_version}")


if not os.path.exists(install_dir):
    url = f"https://ftp.mozilla.org/pub/devedition/releases/{ff_version}/linux-x86_64/en-GB/firefox-{ff_version}.tar.bz2"
    os.makedirs(install_dir)
    r = requests.get(url, allow_redirects=True)
    with open(os.path.join(install_dir, "firefox.tar.bz2"), "wb") as f:
        f.write(r.content)
    print(
        subprocess.check_output(
            ["tar", "xf", "firefox.tar.bz2"],
            cwd=install_dir,
            encoding='utf-8',
            stderr=subprocess.STDOUT
        )
    )


ff_path = os.path.join(install_dir, "firefox", "firefox")

client = Marionette(host="localhost", port=12828, bin=ff_path, headless=True)
try:
    client.start_session()

    client.set_pref("xpinstall.signatures.required", False)

    addons = Addons(client)
    addons.install(extension_path)

    with TestServer('static', 9919):
        client.navigate("http://127.0.1.1:9919/one.html")

        tab2 = client.open(type='tab')
        client.switch_to_window(tab2['handle'])
        client.navigate("http://127.0.1.1:9919/two.html")

        tab3 = client.open(type='window')
        client.switch_to_window(tab3['handle'])
        client.navigate("http://127.0.1.1:9919/three.html")

        # TODO: Find a way to sync without sleep
        time.sleep(1)
        result = subprocess.check_output("tabreport",
                                         encoding='utf-8')
        data = json.loads(result)
        print(json.dumps(data, indent=2))

finally:
    print('Closing client')
    client.close()
    print('Cleaning up client')
    client.cleanup()
