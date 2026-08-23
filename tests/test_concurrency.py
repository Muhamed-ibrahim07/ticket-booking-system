import threading
import requests
import time

URL = 'http://localhost:5000/api/hold_seat'


def attempt_hold(i, results):
    payload = {'show_id': 1, 'seat_id': 1, 'customer_id': i, 'ttl': 600}
    try:
        r = requests.post(URL, json=payload, timeout=5)
        results.append((i, r.status_code))
    except Exception as e:
        results.append((i, 'err'))


def test_concurrent_holds():
    threads = []
    results = []
    for i in range(1, 21):
        t = threading.Thread(target=attempt_hold, args=(i, results))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    success = [r for r in results if r[1] == 200 or r[1] == 201 or r[1] == 202]
    # Expect at most 1 success
    assert len(success) <= 1
