import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from multiprocessing import Process, Event
from threading import Thread
import os.path
import socket
import time
from typing import List, Tuple, Optional


SERVER_ADDRESS = "127.0.1.1"


def run_server(directory: str, address: str, port: int, stop_event: Event) -> None:
    handler_class = partial(SimpleHTTPRequestHandler, directory=directory)
    with ThreadingHTTPServer((address, port), handler_class) as httpd:
        def shutdown():
            stop_event.wait()
            httpd.shutdown()

        t = Thread(target=shutdown)
        t.start()
        httpd.serve_forever()
        t.join()


class HttpServer:
    def __init__(self, directory: str, port: int, address: str = SERVER_ADDRESS):
        self.port = port
        self.address = address
        self.stop_event = Event()
        self.process = Process(
            target=run_server,
            args=(
                os.path.realpath(directory),
                self.address,
                self.port,
                self.stop_event,
            ),
        )

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
                result = sock.connect_ex((self.address, self.port))
            finally:
                sock.close()

            if result == 0:
                return

            if waited_ms >= timeout_ms:
                break

            time.sleep(sleep_ms / 1000.0)
            waited_ms += sleep_ms

        raise Exception(
            "Timed out waiting for http server to start listening for connections"
        )

    def __exit__(self, ex_type, ex_value, ex_traceback):
        self.stop_event.set()
        self.process.join()
        result = self.process.exitcode
        if result != 0 and ex_value is None:
            raise Exception(f"Test server returned {result}")


class MultiHttpServer:
    def __init__(self, args: List[Tuple[str, int, str]]):
        self.servers = [HttpServer(*arg_tuple) for arg_tuple in args]

    def __enter__(self):
        try:
            for server in self.servers:
                server.__enter__()
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def __exit__(self, ex_type, ex_value, ex_traceback):
        first_exception: Optional[Exception] = None
        for server in self.servers:
            try:
                server.__exit__(ex_type, ex_value, ex_traceback)
            except Exception as e:
                first_exception = first_exception or e

        if first_exception is not None:
            raise first_exception
