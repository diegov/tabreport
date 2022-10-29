import os
import sys
import json
import subprocess
import requests

from packaging import version
from packaging.version import Version
from typing import List, Tuple, Dict, Any

from marionette_driver.marionette import Marionette
from marionette_driver.addons import Addons


FF_RELEASES_BASE_URL = "https://ftp.mozilla.org/pub/devedition/releases"


if "XDG_CACHE_HOME" in os.environ:
    cache_home = os.path.expanduser(os.environ["XDG_CACHE_HOME"])
else:
    cache_home = os.path.join(os.path.expanduser("~"), ".cache")

cache_dir = os.path.join(cache_home, "extension_testing")

print(f"Download cache directory set to {cache_dir}", file=sys.stderr)


def _get_versions_from_html(r: requests.Response) -> Dict[str, Any]:
    import bs4
    from bs4 import BeautifulSoup

    versions: List[str] = []
    doc = BeautifulSoup(r.content, "html.parser")
    version_table: bs4.element.Tag = doc.body.table
    name_index = None
    for r in version_table.find_all("tr"):

        if name_index is None:
            headers = r.find_all("th")
            name_index = [
                i for i, v in enumerate(headers) if v.text and v.text.lower() == "name"
            ][0]
        else:
            cells = r.find_all("td")
            version_name = cells[name_index].text if cells[name_index] else None
            versions.append(version_name)

    return {"prefixes": versions}


def _list_firefox_versions() -> Dict[str, Any]:
    r = requests.get(
        f"{FF_RELEASES_BASE_URL}/",
        headers={"Accept": "application/json"},
        allow_redirects=True,
    )
    r.raise_for_status()
    try:
        return json.loads(r.content)  # type: ignore
    except json.JSONDecodeError:
        # Temporary workaround, ftp.mozilla.org has stopped following the
        # Accept header in the req, hopefully it will again in the future.
        return _get_versions_from_html(r)


def get_latest_available_version() -> str:
    version_data = _list_firefox_versions()

    versions: List[Tuple[Version, str]] = []
    for dir_name in version_data["prefixes"]:
        version_string = dir_name.rstrip("/")
        v = version.parse(version_string)
        # "Bad" versions get parsed into `LegacyVersion` objects
        if isinstance(v, Version):
            versions.append((v, version_string))

    versions = sorted(versions)
    latest = versions[-1]

    versions_file = os.path.dirname(
        os.path.join(os.path.realpath(__file__), "firefox_versions")
    )
    with open(versions_file) as f:
        sanity_check = max(version.parse(v.strip()) for v in f if v.strip())

    # We know this version exists, make sure we found something
    # equal or newer than this.
    assert latest[0] >= sanity_check, (
        "Latest version sanity check. "
        + f"Expected >= {sanity_check}, actual {latest[0]}."
    )

    return latest[1]


def get_marionette(ff_version: str, extension_path: str) -> Marionette:
    install_dir = os.path.join(cache_dir, f"ff-{ff_version}")

    if not os.path.exists(install_dir):
        url = f"{FF_RELEASES_BASE_URL}/{ff_version}/linux-x86_64/en-GB/firefox-{ff_version}.tar.bz2"
        os.makedirs(install_dir)
        r = requests.get(url, allow_redirects=True)
        r.raise_for_status()
        with open(os.path.join(install_dir, "firefox.tar.bz2"), "wb") as f:
            f.write(r.content)
        print(
            subprocess.check_output(
                ["tar", "xf", "firefox.tar.bz2"],
                cwd=install_dir,
                encoding="utf-8",
                stderr=subprocess.STDOUT,
            ),
            file=sys.stderr,
        )

    ff_path = os.path.join(install_dir, "firefox", "firefox")

    client = Marionette(host="localhost", port=12828, bin=ff_path, headless=True)
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
