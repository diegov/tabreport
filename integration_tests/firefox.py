import os
import subprocess
import requests


from marionette_driver.marionette import Marionette
from marionette_driver.addons import Addons


if "XDG_CACHE_HOME" in os.environ:
    cache_home = os.path.expanduser(os.environ["XDG_CACHE_HOME"])
else:
    cache_home = os.path.join(os.path.expanduser("~"), ".cache")

cache_dir = os.path.join(cache_home, "extension_testing")

print(f'Download cache directory set to {cache_dir}')


def get_marionette(ff_version: str, extension_path: str) -> Marionette:
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

    client = Marionette(bin=ff_path, headless=True, port=12828)
    try:
        client.start_session()
        client.set_pref("xpinstall.signatures.required", False)

        addons = Addons(client)
        addons.install(extension_path)
    except Exception:
        client.cleanup()
        client.instance = None
        raise

    return client


def close_all_handles(client: Marionette) -> None:
    handles = list(client.window_handles)
    for handle in handles:
        client.switch_to_window(handle)
        client.close()
