def get_key_code(key: str) -> int:
    """
    Encodes `key` using the JDrama algorithm, returning a code
    """
    context = 0
    for char in key:
        context = ord(char) + (context * 3)
        if context > 0xFFFFFFFF:
            context -= 0x100000000
    return context & 0xFFFF


class NameRef(str):
    """
    Implements the JDrama hash into a str like object
    """
    def __hash__(self) -> int:
        return get_key_code(self)