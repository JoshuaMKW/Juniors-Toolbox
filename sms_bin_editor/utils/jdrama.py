from typing import Optional


def get_key_code(key: str, encoding: Optional[str] = None) -> int:
    """
    Encodes `key` using the JDrama algorithm, returning a code
    """
    if encoding is None:
        data = key.encode()
    else:
        try:
            data = key.encode(encoding)
        except UnicodeEncodeError:
            data = key.encode()

    context = 0
    for char in data:
        context = char + (context * 3)
        if context > 0xFFFFFFFF:
            context -= 0x100000000
    return context & 0xFFFF


class NameRef(str):
    """
    Implements the JDrama hash into a str like object
    """
    def __hash__(self) -> int:
        return get_key_code(self, "shift-jis")