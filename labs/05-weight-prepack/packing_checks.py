"""Check weight-buffer reuse and compute amortization on complete request intervals."""

from itertools import accumulate


def check_weight_addresses(mmio, workspace, expected, prepacked):
    writes = [tuple(int(x, 16) for x in line.split()) for line in mmio.read_text().splitlines()]
    observed = [value for addr, value in writes if addr == 0x10010014]
    wanted = [workspace + (tile["col"] * tile["k"] if prepacked else 0)
              for step in expected for tile in step["tiles"]]
    if observed != wanted:
        raise ValueError("B addresses do not match the expected weight layout or reuse order")
    return len(set(observed))


def check_weight_stores(path, counters, mode, steps, packed_bytes, requests):
    """Verify actual bytes written by the CPU before each tile starts DMA."""
    stores = [tuple(map(int, line.split())) for line in path.read_text().splitlines()]
    windows = [tuple(map(int, fields[1:3])) for line in counters.read_text().splitlines()
               if (fields := line.split())[0] == "tile"]
    written = [0] * requests
    if mode == "cpu":
        if stores or windows:
            raise ValueError("CPU baseline used the weight workspace or device")
        return written

    index = 0

    def check_window(previous_end, start, expected):
        nonlocal index
        seen = set()
        while index < len(stores) and stores[index][0] < start:
            cycle, offset, mask, word = stores[index]
            if cycle <= previous_end or offset % 4 or not 0 < mask < 16:
                raise ValueError("weight store overlaps DMA or has invalid lanes")
            for lane in range(4):
                if mask & (1 << lane):
                    pos = offset + lane
                    if (not 0 <= pos < len(expected) or pos in seen
                            or ((word >> (8 * lane)) & 255) != expected[pos]):
                        raise ValueError("wrong or repeated weight byte on the RAM bus")
                    seen.add(pos)
            index += 1
        if len(seen) != len(expected):
            raise ValueError("weight preparation incomplete before DMA")
        return len(seen)

    tiles = [tile for step in steps for tile in step["tiles"]]
    if len(windows) != requests * len(tiles):
        raise ValueError("wrong number of device transactions")
    if mode == "prepacked":
        written[0] = check_window(-1, windows[0][0], packed_bytes)
    else:
        previous_end = -1
        for i, (start, end) in enumerate(windows):
            tile = tiles[i % len(tiles)]
            offset = tile["col"] * tile["k"]
            block = packed_bytes[offset:offset + tile["n"] * tile["k"]]
            written[i // len(tiles)] += check_window(previous_end, start, block)
            previous_end = end
    if index != len(stores):
        raise ValueError("unexpected write to resident weights after preparation")
    return written


def amortization(onsite, packed, setup):
    if len(onsite) != len(packed) or len(onsite) < 2 or setup <= 0:
        raise ValueError("expected paired cold and repeated requests and positive setup time")
    savings = [a - b for a, b in zip(onsite, packed)]
    cumulative = list(accumulate(savings))
    # Use the smallest observed warm saving if the repeated requests differ slightly.
    warm = min(savings[1:])
    deficit = max(0, -savings[0])
    if deficit == 0:
        cold_adjusted = 1
    elif warm > 0:
        cold_adjusted = 1 + (deficit + warm - 1) // warm
    else:
        cold_adjusted = None
    return dict(
        onsite_minus_prepacked_cycles=savings,
        cumulative_saved_cycles=cumulative,
        observed_first_nonloss_request=next((i for i, v in enumerate(cumulative, 1) if v >= 0), None),
        min_warm_saving=warm,
        setup_payback_requests=(setup + warm - 1) // warm if warm > 0 else None,
        cold_adjusted_payback_requests=cold_adjusted,
    )
