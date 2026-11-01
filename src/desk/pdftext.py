"""Plain text out of simple PDFs (IMD's Word-generated bulletins), with no PDF library.

    pdf_text(data: bytes) -> str

Reads every object (including compressed object streams), walks the page tree in order, inflates each page's
content streams and decodes the text operators (Tj, TJ, ', ") with the page's fonts: WinAnsi single-byte fonts
as cp1252, Type0 / Identity-H fonts through their ToUnicode CMap. A move to a new baseline starts a new line;
a wide TJ gap becomes a space. Enough for reading bulletins; not a general PDF renderer.
"""

from __future__ import annotations

import re
import zlib

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
_REF = re.compile(rb"(\d+)\s+0\s+R")


def _inflate(raw: bytes, head: bytes) -> bytes:
    if b"/FlateDecode" not in head:
        return raw
    for cut in (raw, raw.rstrip(b"\r\n")):
        try:
            return zlib.decompress(cut)
        except zlib.error:
            pass
    d = zlib.decompressobj()
    try:
        return d.decompress(raw)
    except zlib.error:
        return b""


def _split(body: bytes) -> tuple[bytes, bytes | None]:
    """(dictionary part, decoded stream or None) of one object body."""
    m = re.search(rb"stream\r?\n", body)
    if not m or b"<<" not in body[: m.start()]:
        return body, None
    head = body[: m.start()]
    end = body.rfind(b"endstream")
    raw = body[m.end(): end if end > 0 else len(body)]
    return head, _inflate(raw, head)


def _objects(data: bytes) -> dict[int, tuple[bytes, bytes | None]]:
    objs: dict[int, tuple[bytes, bytes | None]] = {}
    for m in _OBJ.finditer(data):
        objs[int(m.group(1))] = _split(m.group(3))
    for head, stream in list(objs.values()):            # compressed object streams
        if stream is None or b"/ObjStm" not in head:
            continue
        n = int(re.search(rb"/N\s+(\d+)", head).group(1))
        first = int(re.search(rb"/First\s+(\d+)", head).group(1))
        nums = list(map(int, stream[:first].split()))
        pairs = [(nums[i], nums[i + 1]) for i in range(0, 2 * n, 2)]
        for k, (num, off) in enumerate(pairs):
            end = pairs[k + 1][1] if k + 1 < len(pairs) else len(stream) - first
            objs.setdefault(num, (stream[first + off: first + end], None))
    return objs


def _deref(objs, ref: bytes) -> tuple[bytes, bytes | None]:
    m = _REF.match(ref.strip())
    return objs.get(int(m.group(1)), (b"", None)) if m else (ref, None)


def _dict_entry(head: bytes, key: bytes) -> bytes | None:
    """The raw value of /key in a dictionary: a reference, a nested <<dict>>, an [array] or a name."""
    i = head.find(b"/" + key)
    while i >= 0 and head[i + len(key) + 1: i + len(key) + 2].isalnum():
        i = head.find(b"/" + key, i + 1)
    if i < 0:
        return None
    s = head[i + len(key) + 1:].lstrip()
    if s.startswith(b"<<"):
        depth, j = 0, 0
        while j < len(s):
            if s.startswith(b"<<", j):
                depth += 1
                j += 2
            elif s.startswith(b">>", j):
                depth -= 1
                j += 2
                if depth == 0:
                    return s[:j]
            else:
                j += 1
        return s
    if s.startswith(b"["):
        return s[: s.find(b"]") + 1]
    m = _REF.match(s)
    if m:
        return m.group(0)
    m = re.match(rb"/?[^\s/<>\[\]()]+", s)
    return m.group(0) if m else None


def _resolve_dict(objs, raw: bytes | None) -> bytes:
    if raw is None:
        return b""
    return _deref(objs, raw)[0] if _REF.match(raw.strip()) else raw


def _cmap(data: bytes) -> dict[int, str]:
    out: dict[int, str] = {}
    hexs = lambda h: bytes.fromhex(h.decode()).decode("utf-16-be", "replace")
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            out[int(src, 16)] = hexs(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", block):
            lo, hi = int(lo, 16), int(hi, 16)
            if dst.startswith(b"["):
                for k, d in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", dst)):
                    out[lo + k] = hexs(d)
            else:
                base = bytes.fromhex(dst[1:-1].decode())
                for k in range(hi - lo + 1):
                    b = bytearray(base)
                    b[-1] = (b[-1] + k) & 0xFF
                    out[lo + k] = bytes(b).decode("utf-16-be", "replace")
    return out


class _Font:
    def __init__(self, objs, head: bytes):
        self.two_byte = b"/Type0" in head or b"Identity-H" in head
        tu = _dict_entry(head, b"ToUnicode")
        self.map = _cmap(_deref(objs, tu)[1] or b"") if tu else {}

    def decode(self, raw: bytes) -> str:
        if self.two_byte:
            codes = [raw[i] << 8 | raw[i + 1] for i in range(0, len(raw) - 1, 2)]
            return "".join(self.map.get(c, "") for c in codes)
        if self.map:
            return "".join(self.map.get(b, raw[i: i + 1].decode("cp1252", "replace")) for i, b in enumerate(raw))
        return raw.decode("cp1252", "replace")


_TOKEN = re.compile(rb"\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)|<[0-9A-Fa-f\s]*>|\[|\]|/[^\s/<>\[\]()]+|[-+]?\d*\.?\d+|[A-Za-z'\"*]+")
_ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}


def _literal(tok: bytes) -> bytes:
    s, out, i = tok[1:-1], bytearray(), 0
    while i < len(s):
        c = s[i: i + 1]
        if c == b"\\" and i + 1 < len(s):
            n = s[i + 1: i + 2]
            if n in _ESC:
                out += _ESC[n]
                i += 2
                continue
            m = re.match(rb"[0-7]{1,3}", s[i + 1:])
            if m:
                out.append(int(m.group(0), 8) & 0xFF)
                i += 1 + len(m.group(0))
                continue
            i += 1
            continue
        out += c
        i += 1
    return bytes(out)


def _page_text(objs, content: bytes, fonts: dict[bytes, _Font]) -> str:
    """Text in content order; a new line whenever the baseline moves (Word writes one line in many runs)."""
    out: list[str] = []
    stack: list = []
    font = None
    y = line_y = 0.0
    last_y = None

    def emit(text: str) -> None:
        nonlocal last_y
        if not text:
            return
        if last_y is not None and abs(y - last_y) > 6.0:      # superscripts ("26th") sit ~3-5 pt up: same line
            out.append("\n")
        out.append(text)
        last_y = y

    num = lambda t: float(t) if re.match(rb"[-+]?\d*\.?\d+$", t) else 0.0
    for tok in _TOKEN.findall(content):
        if tok.startswith((b"(", b"<")) or tok in (b"[", b"]") or tok.startswith(b"/") or re.match(rb"[-+]?\d*\.?\d+$", tok):
            stack.append(tok)
            continue
        op = tok
        if op == b"Tf" and len(stack) >= 2:
            font = fonts.get(stack[-2][1:])
        elif op == b"BT":
            y = line_y = 0.0
        elif op == b"Tm" and len(stack) >= 6:
            y = line_y = num(stack[-1])
        elif op in (b"Td", b"TD") and len(stack) >= 2:
            line_y += num(stack[-1])
            y = line_y
        elif op == b"T*":
            line_y -= 12.0
            y = line_y
        elif op in (b"Tj", b"'", b'"'):
            if op != b"Tj":
                line_y -= 12.0
                y = line_y
            emit(_decode_str(stack[-1], font) if stack else "")
        elif op == b"TJ":
            arr = stack[stack.index(b"[") + 1:] if b"[" in stack else stack
            parts = []
            for t in arr:
                if t.startswith((b"(", b"<")):
                    parts.append(_decode_str(t, font))
                elif re.match(rb"[-+]?\d*\.?\d+$", t) and float(t) < -180:
                    parts.append(" ")
            emit("".join(parts))
        stack = []
    return "".join(out)


def _decode_str(tok: bytes, font: _Font | None) -> str:
    raw = bytes.fromhex(re.sub(rb"\s", b"", tok[1:-1]).decode() + ("0" if len(re.sub(rb"\s", b"", tok[1:-1])) % 2 else "")) \
        if tok.startswith(b"<") else _literal(tok)
    return font.decode(raw) if font else raw.decode("cp1252", "replace")


def _pages(objs) -> list[bytes]:
    cat = next((h for h, s in objs.values() if re.search(rb"/Type\s*/Catalog", h)), None)
    if cat is None:
        return []
    out: list[bytes] = []

    def walk(ref: bytes, depth: int = 0):
        head = _deref(objs, ref)[0]
        if depth > 20:
            return
        if re.search(rb"/Type\s*/Pages", head):
            kids = _dict_entry(head, b"Kids") or b"[]"
            for k in _REF.findall(kids):
                walk(k + b" 0 R", depth + 1)
        elif re.search(rb"/Type\s*/Page\b", head):
            out.append(head)
    walk(_dict_entry(cat, b"Pages") or b"")
    return out


def pdf_text(data: bytes) -> str:
    objs = _objects(data)
    pages = []
    for head in _pages(objs):
        res = _resolve_dict(objs, _dict_entry(head, b"Resources"))
        fdict = _resolve_dict(objs, _dict_entry(res, b"Font"))
        fonts = {name[1:]: _Font(objs, _deref(objs, ref)[0]) for name, ref in re.findall(rb"(/[^\s/<>\[\]]+)\s+(\d+\s+0\s+R)", fdict)}
        c = _dict_entry(head, b"Contents") or b""
        refs = [r + b" 0 R" for r in _REF.findall(c)]
        content = b"\n".join(_deref(objs, r)[1] or b"" for r in refs)
        pages.append(_page_text(objs, content, fonts))
    text = "\n".join(pages)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
