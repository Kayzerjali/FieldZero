"""
Ring buffer correctness, including under concurrent read/write.

The concurrency test is the load-bearing one: the whole point of the ring buffer
is that a reader can take a snapshot while the acquisition thread is mid-write
without the DAQ ever stalling. If that has a race, it will show up in the lab as
occasional glitched traces and nothing else, which is exactly the kind of bug
that is impossible to chase after the fact.
"""

import threading

import numpy as np
import pytest

from fieldzero.datasource import RingBuffer


def test_returns_samples_in_chronological_order():
    rb = RingBuffer(2, capacity=10)
    rb.write(np.array([[1, 2, 3], [10, 20, 30]]))
    out, first = rb.latest(3)
    assert np.array_equal(out, [[1, 2, 3], [10, 20, 30]])
    assert first == 0


def test_partial_fill_returns_only_what_exists():
    rb = RingBuffer(1, capacity=100)
    rb.write(np.arange(5).reshape(1, 5))
    out, first = rb.latest(50)
    assert out.shape == (1, 5)
    assert first == 0


def test_empty_buffer_returns_empty():
    rb = RingBuffer(3, capacity=10)
    out, first = rb.latest(5)
    assert out.shape == (3, 0)
    assert first == 0


def test_wraparound_preserves_order():
    rb = RingBuffer(1, capacity=5)
    rb.write(np.arange(8).reshape(1, 8))  # wraps: 5,6,7 overwrite 0,1,2
    out, first = rb.latest(5)
    assert np.array_equal(out[0], [3, 4, 5, 6, 7])
    assert first == 3  # absolute index of the oldest surviving sample


def test_write_larger_than_capacity_keeps_newest():
    rb = RingBuffer(1, capacity=4)
    rb.write(np.arange(10).reshape(1, 10))
    out, first = rb.latest(4)
    assert np.array_equal(out[0], [6, 7, 8, 9])
    assert first == 6
    assert rb.total_written == 10


def test_many_small_writes_stay_contiguous():
    rb = RingBuffer(1, capacity=7)
    for i in range(20):
        rb.write(np.array([[i]]))
    out, first = rb.latest(7)
    assert np.array_equal(out[0], [13, 14, 15, 16, 17, 18, 19])
    assert first == 13


def test_latest_zero_and_negative():
    rb = RingBuffer(1, capacity=5)
    rb.write(np.arange(5).reshape(1, 5))
    assert rb.latest(0)[0].shape == (1, 0)
    assert rb.latest(-3)[0].shape == (1, 0)


def test_concurrent_reads_never_see_a_torn_window():
    """
    The writer emits a strictly increasing counter. Any snapshot the reader takes
    must therefore be a run of consecutive integers — if a read ever straddled a
    partially-completed write, the run would break. Also asserts the returned
    absolute index matches the data, so the time axis cannot silently drift.
    """
    rb = RingBuffer(1, capacity=512)
    stop = threading.Event()
    counter = 0

    def writer():
        nonlocal counter
        while not stop.is_set():
            chunk = np.arange(counter, counter + 37).reshape(1, 37)
            counter += 37
            rb.write(chunk)

    t = threading.Thread(target=writer, daemon=True)
    t.start()

    failures = []
    for _ in range(3000):
        out, first = rb.latest(200)
        if out.shape[1] == 0:
            continue
        row = out[0]
        if not np.array_equal(row, np.arange(row[0], row[0] + row.size)):
            failures.append(("non-contiguous", row[:8].tolist()))
        if row[0] != first:
            failures.append(("index mismatch", float(row[0]), first))

    stop.set()
    t.join(timeout=2)
    assert not failures, failures[:5]
