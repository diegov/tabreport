#!/usr/bin/env python3

import json
import sys
import struct
import time
import random


def send_event(event):
    content = json.dumps(event).encode('utf-8')
    length = struct.pack('@I', len(content))
    sys.stdout.buffer.write(length)
    sys.stdout.buffer.write(content)
    sys.stdout.buffer.flush()


while True:
    for i in range(random.randint(1, 4)):
        tab_id = random.randint(0, 30)
        action = random.choice(['update', 'remove'])
        if action == 'remove':
            send_event({"action": "remove", "tab_id": tab_id})
        else:
            title = "Tab with index {}".format(tab_id)
            send_event({
                "action": "update",
                "tab_id": tab_id,
                "title": title,
                "window_id": random.randint(1, 200),
                "url": "http://www.test{}.com".format(random.randint(1, 50))
            })

    time.sleep(0.1 + random.randint(0, 100) / 50.0)
