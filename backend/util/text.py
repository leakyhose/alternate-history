"""Text utilities for the alternate history simulation."""

# Map of accented characters to ASCII equivalents
_TRANSLIT_MAP = {
    'A': 'A', 'A': 'A', 'A': 'A', 'A': 'A', 'A': 'A', 'A': 'A', 'AE': 'AE',
    'C': 'C', 'E': 'E', 'E': 'E', 'E': 'E', 'E': 'E',
    'I': 'I', 'I': 'I', 'I': 'I', 'I': 'I',
    'D': 'D', 'N': 'N',
    'O': 'O', 'O': 'O', 'O': 'O', 'O': 'O', 'O': 'O', 'O': 'O',
    'U': 'U', 'U': 'U', 'U': 'U', 'U': 'U',
    'Y': 'Y', 'TH': 'TH', 'ss': 'ss',
    'a': 'a', 'a': 'a', 'a': 'a', 'a': 'a', 'a': 'a', 'a': 'a', 'ae': 'ae',
    'c': 'c', 'e': 'e', 'e': 'e', 'e': 'e', 'e': 'e',
    'i': 'i', 'i': 'i', 'i': 'i', 'i': 'i',
    'd': 'd', 'n': 'n',
    'o': 'o', 'o': 'o', 'o': 'o', 'o': 'o', 'o': 'o', 'o': 'o',
    'u': 'u', 'u': 'u', 'u': 'u', 'u': 'u',
    'y': 'y', 'th': 'th', 'y': 'y',
    'OE': 'OE', 'oe': 'oe', 'S': 'S', 's': 's', 'Z': 'Z', 'z': 'z',
    'f': 'f', 'Y': 'Y',
    # Original map with proper accented chars
    '\u00c0': 'A', '\u00c1': 'A', '\u00c2': 'A', '\u00c3': 'A', '\u00c4': 'A', '\u00c5': 'A', '\u00c6': 'AE',
    '\u00c7': 'C', '\u00c8': 'E', '\u00c9': 'E', '\u00ca': 'E', '\u00cb': 'E',
    '\u00cc': 'I', '\u00cd': 'I', '\u00ce': 'I', '\u00cf': 'I',
    '\u00d0': 'D', '\u00d1': 'N',
    '\u00d2': 'O', '\u00d3': 'O', '\u00d4': 'O', '\u00d5': 'O', '\u00d6': 'O', '\u00d8': 'O',
    '\u00d9': 'U', '\u00da': 'U', '\u00db': 'U', '\u00dc': 'U',
    '\u00dd': 'Y', '\u00de': 'TH', '\u00df': 'ss',
    '\u00e0': 'a', '\u00e1': 'a', '\u00e2': 'a', '\u00e3': 'a', '\u00e4': 'a', '\u00e5': 'a', '\u00e6': 'ae',
    '\u00e7': 'c', '\u00e8': 'e', '\u00e9': 'e', '\u00ea': 'e', '\u00eb': 'e',
    '\u00ec': 'i', '\u00ed': 'i', '\u00ee': 'i', '\u00ef': 'i',
    '\u00f0': 'd', '\u00f1': 'n',
    '\u00f2': 'o', '\u00f3': 'o', '\u00f4': 'o', '\u00f5': 'o', '\u00f6': 'o', '\u00f8': 'o',
    '\u00f9': 'u', '\u00fa': 'u', '\u00fb': 'u', '\u00fc': 'u',
    '\u00fd': 'y', '\u00fe': 'th', '\u00ff': 'y',
    '\u0152': 'OE', '\u0153': 'oe', '\u0160': 'S', '\u0161': 's', '\u017d': 'Z', '\u017e': 'z',
    '\u0192': 'f', '\u0178': 'Y'
}


def transliterate(text: str) -> str:
    """Convert accented characters to ASCII equivalents."""
    return ''.join(_TRANSLIT_MAP.get(c, c) for c in text)
