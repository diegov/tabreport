from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
import multiprocessing
from multiprocessing import Process, Event
from threading import Thread
import os.path
import socket
import time


SERVER_ADDRESS = '127.0.1.1'


def run_server(directory: str, port: int, stop_event: Event) -> None:
    multiprocessing.Event()
    handler_class = partial(SimpleHTTPRequestHandler, directory=directory)
    with ThreadingHTTPServer((SERVER_ADDRESS, port), handler_class) as httpd:
        def shutdown():
            stop_event.wait()
            httpd.shutdown()

        t = Thread(target=shutdown)
        t.start()
        httpd.serve_forever()
        t.join()


class TestServer:
    def __init__(self, directory: str, port: int):
        self.port = port
        self.stop_event = Event()
        self.process = Process(target=run_server,
                               args=(os.path.realpath(directory),
                                     self.port, self.stop_event))

    def __enter__(self):
        self.process.start()
        self._wait_for_server()

    def _wait_for_server(self, timeout_ms=5000) -> None:
        waited_ms = 0.0
        timeout_ms = timeout_ms + 0.0
        sleep_ms = 100
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                result = sock.connect_ex((SERVER_ADDRESS, self.port))
            finally:
                sock.close()

            if result == 0:
                return

            if waited_ms >= timeout_ms:
                break

            time.sleep(sleep_ms / 1000.0)
            waited_ms += sleep_ms

        raise Exception("Timed out waiting for http server to start listening for connections")

    def __exit__(self, ex_type, ex_value, ex_traceback):
        self.stop_event.set()
        self.process.join()
        result = self.process.exitcode
        if result != 0 and ex_value is None:
            raise Exception(f"Test server returned {result}")
