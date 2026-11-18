"""Build the little-endian RV32 copy-model package and the independent request input."""

import struct
import zlib

HEADER = struct.Struct("<4sIIII")
COMMON = (
    "tokens.weight", "positions.weight", "attn_norm.weight", "attn_norm.bias",
    "qkv.weight", "qkv.bias", "attn_out.weight", "attn_out.bias",
    "ffn_norm.weight", "ffn_norm.bias", "down.bias", "final_norm.weight",
    "final_norm.bias", "head.weight", "head.bias",
)


def floats(tensor):
    values = tensor.flatten().tolist()
    return struct.pack(f"<{len(values)}f", *values)


def package(width, payload, version=1):
    return HEADER.pack(b"AMP1", version, width, len(payload), zlib.crc32(payload)) + payload


def export_package(model, quant):
    tensors = model.state_dict()
    parts = [floats(quant.sx), floats(quant.sw)]
    parts.extend(floats(tensors[name]) for name in COMMON)
    parts.extend([floats(quant.bias), floats(tensors["down.weight"]),
                  bytes(x & 255 for x in quant.wq.flatten().tolist())])
    return package(len(quant.sw), b"".join(parts))


def make_inputs(prompt, a, b, *, version=1, extra_invalid=()):
    # A-copy has its own address. Truncated B ends inside a real, shorter span.
    bad_crc = bytearray(a)  # Same width as the resident A, with one damaged weight byte.
    bad_crc[-1] ^= 1
    bad_scale = bytearray(b[HEADER.size:])
    struct.pack_into("<I", bad_scale, 4 * 24, 0x7fc00000)  # final channel, valid CRC
    blobs = {"A": a, "A-copy": a, "B": b, "flipped": bad_crc, "truncated": b[:-1],
             "bad-width": package(28, b[HEADER.size:], version), "nan-scale": package(24, bad_scale, version)}
    # (input copy, expected model, expected loader status, expected cache hit)
    cases = [
        ("A", 32, 0, False), ("A-copy", 32, 0, True), ("B", 24, 0, False),
        ("A", 32, 0, False), ("flipped", None, 3, None), ("truncated", None, 1, None),
        ("bad-width", None, 2, None), ("nan-scale", None, 4, None), ("A", 32, 0, True),
    ]
    for name, blob, status in extra_invalid:
        blobs[name] = blob
        cases.insert(-1, (name, None, status, None))
    return encode_requests(prompt, cases, blobs), cases


def encode_requests(prompt, cases, blobs):
    inputs = bytearray([*prompt, len(cases)])
    inputs.extend(bytes(-len(inputs) % 4))
    header = len(inputs)
    inputs.extend(bytes(8 * len(cases)))
    spans = {}
    for name, blob in blobs.items():
        inputs.extend(bytes(-len(inputs) % 4))
        spans[name] = len(inputs), len(blob)
        inputs.extend(blob)
    for i, (name, *_) in enumerate(cases):
        struct.pack_into("<II", inputs, header+8*i, *spans[name])
    return inputs
