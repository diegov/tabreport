#!/usr/bin/env python3

import sys
import os
import os.path
import subprocess
import time
import json
from typing import Dict, Any, List, Optional
from test_server import MultiHttpServer
from firefox import get_marionette, close_all_handles
import unittest
from hamcrest import assert_that, has_length


SLEEP_TIME = 0.25


def get_tabs() -> List[Dict[str, Any]]:
    # TODO: Find a way to sync without sleep
    time.sleep(SLEEP_TIME)

    result = subprocess.check_output("tabreport", encoding='utf-8')
    return json.loads(result)  # type: ignore


FF_VERSION = sys.argv[1]
EXTENSION_PATH = os.path.realpath(sys.argv[2])
sys.argv = sys.argv[2:]


print(f"Running tests for extension {EXTENSION_PATH} using Firefox {FF_VERSION}")
if not os.path.isfile(EXTENSION_PATH):
    raise FileNotFoundError(EXTENSION_PATH)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = get_marionette(FF_VERSION, EXTENSION_PATH)

    @classmethod
    def tearDownClass(cls):
        close_all_handles(cls.client)
        cls.client.cleanup()
        # Fix marionette's double cleanup problem. I guess we're not supposed
        # to clean stuff up and we should just let it be handled by __del__?
        # That's not a good approach when we've launched a child process, so
        # we call cleanup ourselves and just fix this.
        cls.client.instance = None

    def tearDown(self):
        close_all_handles(self.client)

    def get_unique(self, tab_data: List[Dict[str, Any]], url: str) -> Dict[str, Any]:
        candidate: Optional[Dict[str, Any]] = None

        for val in tab_data:
            if val['url'] == url:
                if candidate is None:
                    candidate = val
                else:
                    raise Exception(f"More than one tab with URL {url}")

        self.assertIsNotNone(candidate)
        # make MyPy happy. It would be better assertIsNotNone signature
        # was Optional[T] -> T so we could return from that, but it isn't
        assert candidate is not None
        return candidate

    def activate_tab(self, tab_info: Dict[str, Any]) -> None:
        subprocess.check_output(["tabreport", str(tab_info['tab_id'])],
                                encoding='utf-8')
        time.sleep(SLEEP_TIME)

        # Activate the chrome window manually, since we have no other way
        # to do it. Firefox will request focus, but marionette doesn't seem to
        # provide any functionality to detect that, so we'd need to run this
        # under xvfb or similar and catch it from the window system side, and
        # it's too much work.
        # TODO: See if Marionette.execute_script lets us solve this via JS.
        all_handles = []
        with self.client.using_context(self.client.CONTEXT_CHROME):
            original_handle = self.client.current_window_handle
            for handle in self.client.window_handles:
                all_handles.append(handle)

        for handle in sorted(all_handles):
            self.client.switch_to_window(handle)
            # This is only valid if all the URLs are unique, so
            # we've to write all the tests that way
            if self.client.get_url() == tab_info['url']:
                return

        self.client.switch_to_window(original_handle)

    def test_tabreport_multiple_tabs(self):
        with MultiHttpServer([('static', 9919, '127.0.121.1'),
                              ('static', 9919, '127.0.99.1')]):
            self.client.navigate("http://127.0.121.1:9919/one.html")
            page1 = self.client.current_window_handle

            page2 = self.client.open(type='tab')['handle']
            self.client.switch_to_window(page2)
            self.client.navigate("http://127.0.99.1:9919/two.html")

            page3 = self.client.open(type='window')['handle']
            self.client.switch_to_window(page3)
            self.client.navigate("http://127.0.121.1:9919/three.html")

            data = get_tabs()

            assert_that(data, has_length(3))

            tab1 = self.get_unique(data, 'http://127.0.121.1:9919/one.html')
            self.assertEqual(tab1['title'], 'One Site')

            tab2 = self.get_unique(data, 'http://127.0.99.1:9919/two.html')
            self.assertEqual(tab2['title'], 'Two Site')

            tab3 = self.get_unique(data, 'http://127.0.121.1:9919/three.html')
            self.assertEqual(tab3['title'], 'Another site')

            self.assertEqual(tab1['window_id'], tab2['window_id'])
            self.assertNotEqual(tab1['window_id'], tab3['window_id'])

            self.client.switch_to_window(page1)
            self.client.close()

            data = get_tabs()

            assert_that(data, has_length(2))

            tab2 = self.get_unique(data, 'http://127.0.99.1:9919/two.html')
            self.assertEqual(tab2['title'], 'Two Site')

            tab3 = self.get_unique(data, 'http://127.0.121.1:9919/three.html')
            self.assertEqual(tab3['title'], 'Another site')

            self.client.switch_to_window(page2)
            self.client.navigate('http://127.0.121.1:9919/one.html')

            data = get_tabs()

            assert_that(data, has_length(2))

            tab2 = self.get_unique(data, 'http://127.0.121.1:9919/one.html')
            self.assertEqual(tab2['title'], 'One Site')

            tab3 = self.get_unique(data, 'http://127.0.121.1:9919/three.html')
            assert tab3['title'] == 'Another site'

            self.client.switch_to_window(page3)
            self.client.navigate('http://127.0.121.1:9919/one.html')

            data = get_tabs()

            assert_that(data, has_length(2))

            self.assertEqual(data[0]['url'], 'http://127.0.121.1:9919/one.html')
            self.assertEqual(data[0]['title'], 'One Site')
            self.assertEqual(data[1]['url'], 'http://127.0.121.1:9919/one.html')
            self.assertEqual(data[1]['title'], 'One Site')
            self.assertNotEqual(data[0]['window_id'], data[1]['window_id'])

    def test_close_all_but_one(self):
        all_urls = ['http://127.0.{}.1:9919/{}'.format(ip, resource)
                    for ip in range(98, 101)
                    for resource in ['one.html', 'two.html', 'three.html',
                                     'four.html']]

        with MultiHttpServer([('static', 9919, '127.0.98.1'),
                              ('static', 9919, '127.0.99.1'),
                              ('static', 9919, '127.0.100.1')]):
            self.client.navigate(all_urls[0])

            for url in all_urls[1:]:
                new_page = self.client.open(type='tab')['handle']
                self.client.switch_to_window(new_page)
                self.client.navigate(url)

            data = get_tabs()

            assert_that(data, has_length(len(all_urls)))

            # Close all but this
            to_keep = 'http://127.0.99.1:9919/two.html'
            handles = list(self.client.window_handles)
            for handle in handles:
                self.client.switch_to_window(handle)
                if self.client.get_url() != to_keep:
                    self.client.close()

            data = get_tabs()
            assert_that(data, has_length(1))
            tab = self.get_unique(data, to_keep)
            self.assertEqual(tab['title'], 'Two Site')

    def test_focus_tabs(self):
        with MultiHttpServer([('static', 9919, '127.0.7.1'),
                              ('static', 12830, '127.0.8.1')]):
            self.client.navigate('http://127.0.7.1:9919/one.html')

            new_page = self.client.open(type='tab')['handle']
            self.client.switch_to_window(new_page)
            self.client.navigate('http://127.0.8.1:12830/four.html')

            new_page = self.client.open(type='tab')['handle']
            self.client.switch_to_window(new_page)
            self.client.navigate('http://127.0.7.1:9919/four.html')

            new_page = self.client.open(type='window')['handle']
            self.client.switch_to_window(new_page)
            self.client.navigate('http://127.0.7.1:9919/three.html')

            data = get_tabs()
            assert_that(data, has_length(4))

            url = self.client.get_url()
            self.assertEqual(url, 'http://127.0.7.1:9919/three.html')

            target_url = 'http://127.0.8.1:12830/four.html'
            tab_info = self.get_unique(data, target_url)
            self.activate_tab(tab_info)

            url = self.client.get_url()
            self.assertEqual(url, target_url)

            target_url = 'http://127.0.7.1:9919/three.html'
            tab_info = self.get_unique(data, target_url)
            self.activate_tab(tab_info)

            url = self.client.get_url()
            self.assertEqual(url, target_url)

            target_url = 'http://127.0.8.1:12830/four.html'
            tab_info = self.get_unique(data, target_url)
            self.activate_tab(tab_info)

            url = self.client.get_url()
            self.assertEqual(url, target_url)


if __name__ == '__main__':
    unittest.main()
