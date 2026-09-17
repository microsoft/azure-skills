"""Bounded lexical, OOXML-part and image-header adapters; no conversion."""
from __future__ import annotations

import codecs
from html.parser import HTMLParser
import io
import json
from pathlib import PurePosixPath
import re
import struct
import sys
import zipfile
import zlib

XML_VERSION = "0.7.1"
MAX_TEXT = 2 * 1024 * 1024
MAX_ENTRIES = 256
MAX_INFLATED = 16 * 1024 * 1024
MAX_RATIO = 100
MAX_NODES = 100_000
MAX_DEPTH = 64
MAX_IMAGE_PIXELS = 100_000_000
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE = {
    "docx": ("/word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    "pptx": ("/ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
    "xlsx": ("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
}


class AdapterBlocked(ValueError):
    """Fixed content-free reason; callers never forward parser exceptions."""


def facts(**values):
    return {
        "page_count": "not-applicable",
        "text_characters": "not-assessed", "text_available": "not-assessed",
        "total_images": "not-assessed", "total_drawings": "not-assessed",
        "table_structure": "not-assessed", "layout_relationships": "not-assessed",
        "input_profile": "unknown", "answerability": "not-assessed",
        "ocr_need": "not-assessed", **values,
    }


def text_facts(count, basis, **values):
    return facts(text_characters=count, text_available=count > 0, text_basis=basis, **values)


class HTMLCounts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.characters = 0
        self.tags = {"img": 0, "table": 0, "tr": 0, "td": 0, "th": 0}
        self.suppressed = []
        self.nodes = 0

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise AdapterBlocked("document-node-limit")
        if tag in {"script", "style"}:
            self.suppressed.append(tag)
        if not self.suppressed and tag in self.tags:
            self.tags[tag] += 1

    def handle_endtag(self, tag):
        if self.suppressed and self.suppressed[-1] == tag:
            self.suppressed.pop()

    def handle_data(self, data):
        if not self.suppressed:
            self.characters += len(data)


def assess_text(data, hint):
    if len(data) > MAX_TEXT:
        raise AdapterBlocked("text-input-limit")
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise AdapterBlocked("unsupported-text-encoding-or-format") from None
    if any(ord(char) < 32 and char not in "\t\r\n" for char in text):
        raise AdapterBlocked("unsupported-binary-format")
    kind = "text" if hint == "auto" else hint
    if kind not in {"text", "markdown", "html", "json"}:
        raise AdapterBlocked("format-hint-mismatch")
    if kind == "json":
        def reject_constant(value):
            raise AdapterBlocked("nonstandard-json")

        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise AdapterBlocked("duplicate-json-key")
                result[key] = value
            return result

        try:
            value = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)
        except AdapterBlocked:
            raise
        except (ValueError, UnicodeError):
            raise AdapterBlocked("invalid-json") from None
        count = nodes = objects = arrays = keys = 0
        pending = [(value, 1)]
        while pending:
            value, depth = pending.pop()
            nodes += 1
            if nodes > MAX_NODES or depth > MAX_DEPTH:
                raise AdapterBlocked("document-node-or-depth-limit")
            if isinstance(value, str):
                count += len(value)
            elif isinstance(value, dict):
                objects += 1
                keys += len(value)
                pending.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list):
                arrays += 1
                pending.extend((item, depth + 1) for item in value)
        return kind, "stdlib-json", text_facts(count, "string-values-only",
                                              objects=objects, arrays=arrays, keys=keys)
    if kind == "html":
        parser = HTMLCounts()
        parser.feed(text)
        parser.close()
        return kind, "stdlib-HTMLParser", text_facts(
            parser.characters, "data-events-excluding-script-style",
            html_elements=parser.tags, validation="tolerant-syntax-not-rendering")
    return kind, "stdlib-utf8", text_facts(
        len(text), "decoded-characters-including-whitespace-and-markup",
        markdown_structure="not-assessed" if kind == "markdown" else "not-applicable")


def xml_parser():
    try:
        import defusedxml
        from defusedxml.ElementTree import fromstring
        from defusedxml.common import DefusedXmlException
        from xml.etree.ElementTree import ParseError
    except ImportError:
        raise AdapterBlocked("office-parser-dependency-missing") from None
    if defusedxml.__version__ != XML_VERSION:
        raise AdapterBlocked("office-parser-version-unsupported")
    return fromstring, (DefusedXmlException, ParseError)


def bounded_xml(data, parse, errors):
    if len(data) > MAX_TEXT:
        raise AdapterBlocked("archive-entry-limit")
    try:
        root = parse(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except errors:
        raise AdapterBlocked("unsafe-or-invalid-office-xml") from None
    pending, nodes = [(root, 1)], 0
    while pending:
        element, depth = pending.pop()
        nodes += 1
        if nodes > MAX_NODES or depth > MAX_DEPTH:
            raise AdapterBlocked("document-node-or-depth-limit")
        pending.extend((child, depth + 1) for child in element)
    return root, nodes


def assess_office(data, hint, parse, errors):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ENTRIES:
                raise AdapterBlocked("archive-entry-count-limit")
            names, total = set(), 0
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if (entry.filename in names or path.is_absolute() or ".." in path.parts
                        or "\\" in entry.filename or ":" in entry.filename):
                    raise AdapterBlocked("unsafe-or-duplicate-archive-entry")
                names.add(entry.filename)
                total += entry.file_size
                if entry.flag_bits & 1:
                    raise AdapterBlocked("encrypted-office-archive")
                if entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise AdapterBlocked("unsupported-archive-compression")
                if (entry.file_size > MAX_TEXT or total > MAX_INFLATED
                        or entry.file_size > MAX_RATIO * max(entry.compress_size, 1)):
                    raise AdapterBlocked("archive-inflation-limit")
                if entry.filename.lower().endswith("vbaproject.bin"):
                    raise AdapterBlocked("macro-package-not-assessed")

            def read_xml(part):
                if part not in names:
                    raise AdapterBlocked("incomplete-office-package")
                with archive.open(part) as source:
                    content = source.read(MAX_TEXT + 1)
                return bounded_xml(content, parse, errors)

            if "[Content_Types].xml" not in names:
                raise AdapterBlocked("unsupported-zip-format")
            types, nodes = read_xml("[Content_Types].xml")
            if types.tag != f"{{{CT}}}Types":
                raise AdapterBlocked("unsupported-office-namespace")
            declared = [(child.get("PartName"), child.get("ContentType")) for child in types]
            if any("macroenabled" in (kind or "").lower() for _, kind in declared):
                raise AdapterBlocked("macro-package-not-assessed")
            kinds = [kind for kind, definition in OFFICE.items() if definition in declared]
            if len(kinds) != 1:
                raise AdapterBlocked("unsupported-office-profile")
            kind = kinds[0]
            if hint not in {"auto", kind}:
                raise AdapterBlocked("format-hint-mismatch")
            main = OFFICE[kind][0][1:]
            root, used = read_xml(main)
            nodes += used
            expected = {"docx": f"{{{W}}}document", "pptx": f"{{{P}}}presentation",
                        "xlsx": f"{{{S}}}workbook"}[kind]
            if root.tag != expected:
                raise AdapterBlocked("unsupported-office-namespace")
            patterns = {
                "docx": r"word/document\.xml",
                "pptx": r"ppt/slides/slide[0-9]+\.xml",
                "xlsx": r"xl/(worksheets/sheet[0-9]+|sharedStrings|tables/table[0-9]+)\.xml",
            }
            parts = sorted(part for part in names if re.fullmatch(patterns[kind], part))
            if not parts:
                raise AdapterBlocked("office-content-parts-unavailable")
            characters = tables = image_refs = paragraphs = formulas = cells = 0
            for part in parts:
                tree, used = (root, 0) if part == main else read_xml(part)
                nodes += used
                if nodes > MAX_NODES:
                    raise AdapterBlocked("document-node-limit")
                allowed_roots = {
                    "docx": {f"{{{W}}}document"}, "pptx": {f"{{{P}}}sld"},
                    "xlsx": {f"{{{S}}}worksheet", f"{{{S}}}sst", f"{{{S}}}table"},
                }[kind]
                if tree.tag not in allowed_roots:
                    raise AdapterBlocked("unsupported-office-namespace")
                for element in tree.iter():
                    if element.tag == {"docx": f"{{{W}}}t", "pptx": f"{{{A}}}t",
                                       "xlsx": f"{{{S}}}t"}[kind]:
                        characters += len(element.text or "")
                    tables += element.tag in {f"{{{W}}}tbl", f"{{{A}}}tbl", f"{{{S}}}table"}
                    image_refs += element.tag == f"{{{A}}}blip"
                    paragraphs += element.tag in {f"{{{W}}}p", f"{{{A}}}p"}
                    formulas += element.tag == f"{{{S}}}f"
                    cells += element.tag == f"{{{S}}}c"
            result = text_facts(
                characters, "stored-text-elements-not-rendered-or-cell-occurrences",
                page_count="not-assessed", inspected_xml_parts=len(parts),
                table_elements=tables, image_reference_elements=image_refs,
                paragraphs=paragraphs if kind != "xlsx" else "not-applicable",
                formula_elements=formulas if kind == "xlsx" else "not-applicable",
                cell_elements=cells if kind == "xlsx" else "not-applicable",
                slide_parts=len(parts) if kind == "pptx" else "not-applicable",
                declared_sheets=sum(e.tag == f"{{{S}}}sheet" for e in root.iter())
                if kind == "xlsx" else "not-applicable",
                coverage={"docx": "main-document-only", "pptx": "all-standard-slide-parts",
                          "xlsx": "standard-worksheet-shared-string-table-parts"}[kind],
                relationships="not-resolved", rendering="not-assessed",
            )
            return kind, f"stdlib-zipfile+defusedxml=={XML_VERSION}", result
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError, zlib.error):
        raise AdapterBlocked("invalid-office-archive") from None


def image_facts(kind, width, height, **values):
    if not width or not height or width * height > MAX_IMAGE_PIXELS:
        raise AdapterBlocked("image-dimension-limit")
    return kind, "stdlib-struct-header", facts(
        width=width, height=height, text_characters="not-assessed",
        text_available="not-assessed", validation="header-only-pixels-not-assessed",
        frame_count="not-assessed", **values)


def assess_png(data):
    if len(data) < 33 or data[8:16] != b"\0\0\0\rIHDR":
        raise AdapterBlocked("invalid-png-header")
    width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data[16:29])
    if (zlib.crc32(data[12:29]) != struct.unpack(">I", data[29:33])[0]
            or compression or filtering or interlace not in (0, 1)
            or depth not in {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8},
                             4: {8, 16}, 6: {8, 16}}.get(color, set())):
        raise AdapterBlocked("invalid-png-header")
    return image_facts("png", width, height, bit_depth=depth, color_type=color)


def assess_jpeg(data):
    position = 2
    for _ in range(4096):
        if position >= len(data) or data[position] != 255:
            raise AdapterBlocked("invalid-jpeg-header")
        while position < len(data) and data[position] == 255:
            position += 1
        if position >= len(data):
            raise AdapterBlocked("invalid-jpeg-header")
        marker = data[position]
        position += 1
        if marker in (0xDA, 0xD9) or position + 2 > len(data):
            raise AdapterBlocked("jpeg-frame-header-unavailable")
        length = int.from_bytes(data[position:position + 2], "big")
        if length < 2 or position + length > len(data):
            raise AdapterBlocked("invalid-jpeg-header")
        if marker in (0xC0, 0xC1, 0xC2):
            if length < 8:
                raise AdapterBlocked("invalid-jpeg-header")
            depth, height, width, components = struct.unpack(">BHHB", data[position + 2:position + 8])
            if length != 8 + 3 * components or not 1 <= components <= 4 or depth not in (8, 12):
                raise AdapterBlocked("invalid-jpeg-header")
            return image_facts("jpeg", width, height, precision=depth, components=components)
        position += length
    raise AdapterBlocked("image-marker-limit")


def assess_document(data, hint, deny_reads):
    for encoding in ("utf-8-sig", "cp437", "ascii", "utf-8"):
        codecs.lookup(encoding)
    office = data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    parse, errors = xml_parser() if office else (None, ())
    sys.addaudithook(deny_reads)
    if office:
        return assess_office(data, hint, parse, errors)
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise AdapterBlocked("legacy-or-encrypted-office-not-assessed")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if hint not in {"auto", "png"}:
            raise AdapterBlocked("format-hint-mismatch")
        return assess_png(data)
    if data.startswith(b"\xff\xd8"):
        if hint not in {"auto", "jpeg"}:
            raise AdapterBlocked("format-hint-mismatch")
        return assess_jpeg(data)
    return assess_text(data, hint)
