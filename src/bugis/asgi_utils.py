from typing import Tuple, Dict, Sequence

type StrOrStrings = (str, Sequence[str])

def decode_headers(headers: Sequence[Tuple[bytes, bytes]]) -> Dict[str, Sequence[str]]:
    result = dict()
    for key, value in headers:
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        l = result.setdefault(key, list())
        l.append(value)
    return {
        k: tuple(v) for k, v in result.items()
    }

def encode_headers(headers: Dict[str, StrOrStrings]) -> Tuple[Tuple[bytes, bytes], ...]:
    result = []
    for key, value in headers.items():
        if isinstance(value, str):
            result.append((key.encode(), value.encode()))
        elif isinstance(value, Sequence):
            for single_value in value:
                result.append((key.encode(), single_value.encode()))
    return tuple(result)