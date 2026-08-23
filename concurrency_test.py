"""Simple concurrency test: fire multiple concurrent requests to hold the same seat."""
import threading
import requests
import time

URL = 'http://localhost:5000/api/hold_seat'


def attempt_hold(i):
    payload = {'show_id': 1, 'seat_id': 1, 'customer_id': i, 'ttl': 600}
    try:
        r = requests.post(URL, json=payload, timeout=5)
        print(i, r.status_code, r.text)
    except Exception as e:
        print(i, 'err', e)


def run_concurrent(n=20):
    threads = []
    for i in range(n):
        t = threading.Thread(target=attempt_hold, args=(i+1,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()


if __name__ == '__main__':
    time.sleep(1)
    run_concurrent(20)
