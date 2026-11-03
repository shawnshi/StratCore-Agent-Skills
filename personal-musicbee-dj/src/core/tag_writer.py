"""Single-writer metadata commits with exact-header recovery and payload verification."""

from contextlib import contextmanager
import hashlib
import importlib
import ipaddress
import os
from pathlib import Path
import shutil
import tempfile
import time
from urllib.parse import urlparse
import uuid

from src.core.local_paths import local_path, local_regular_file
from src.core.tag_inventory import (
    FIELDS,
    acceptable,
    codec,
    incomplete,
    mapped,
    read_json,
    values,
)

mutagen = codec()
ID3 = importlib.import_module("mutagen.id3").ID3
TMOO = importlib.import_module("mutagen.id3").TMOO
TCON = importlib.import_module("mutagen.id3").TCON
TXXX = importlib.import_module("mutagen.id3").TXXX
FLAC = importlib.import_module("mutagen.flac").FLAC
MP3 = importlib.import_module("mutagen.mp3").MP3


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError("Commit deadline exceeded; inspect recovery receipts before retry")


def retry_on_sharing_violation(action, max_attempts=3, delay=0.2, deadline=None):
    """Retry on Windows sharing violation (WinError 32 / ERROR_SHARING_VIOLATION)."""
    last_error = None
    for attempt in range(max_attempts):
        check_deadline(deadline)
        try:
            return action()
        except OSError as exc:
            is_sharing_violation = (
                getattr(exc, "winerror", None) == 32
                or (isinstance(exc, PermissionError) and getattr(exc, "winerror", None) == 32)
            )
            if not is_sharing_violation or attempt == max_attempts - 1:
                raise
            last_error = exc
            time.sleep(delay)
    if last_error:
        raise last_error


def payload_range(path):
    path = Path(path)
    start = header_end(path)
    size = path.stat().st_size
    if path.suffix.lower() == ".mp3" and size >= start + 128:
        with path.open("rb") as f:
            f.seek(-128, 2)
            if f.read(3) == b"TAG":
                return start, size - 128
    return start, size


def digest(path, offset=0, length=None, deadline=None):
    check_deadline(deadline)
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        source.seek(offset)
        remaining = length
        while True:
            check_deadline(deadline)
            chunk_size = 1024 * 1024
            if remaining is not None:
                if remaining <= 0:
                    break
                chunk_size = min(chunk_size, remaining)
            block = source.read(chunk_size)
            if not block:
                break
            h.update(block)
            if remaining is not None:
                remaining -= len(block)
    return h.hexdigest()


def windows_security_descriptor(path):
    """Read owner/group/DACL bytes locally; never log or change source security."""
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("advapi32", use_last_error=True).GetFileSecurityW
    api.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.restype = wintypes.BOOL
    needed = wintypes.DWORD()
    name = "\\\\?\\" + str(Path(path).absolute())
    if (
        not api(name, 7, None, 0, ctypes.byref(needed))
        and ctypes.get_last_error() != 122
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if not needed.value:
        raise ValueError("Missing file security descriptor")
    buffer = ctypes.create_string_buffer(needed.value)
    if not api(name, 7, buffer, needed.value, ctypes.byref(needed)):
        raise ctypes.WinError(ctypes.get_last_error())
    raw = bytearray(buffer.raw[: needed.value])
    if len(raw) > 4:
        import struct
        val = struct.unpack_from('<H', raw, 2)[0]
        # Mask transient SE_DACL_AUTO_INHERITED (0x0400)
        struct.pack_into('<H', raw, 2, val & ~0x0400)
    return bytes(raw)


def security_digest(path):
    """Read only owner/group/DACL; preserve the existing exact-digest contract."""
    if os.name == "nt":
        return hashlib.sha256(windows_security_descriptor(path)).hexdigest()
    info = Path(path).stat()
    return hashlib.sha256(str((info.st_uid, info.st_gid, info.st_mode)).encode()).hexdigest()


def staging_file(source, prefix=".music-tag-stage-", deadline=None):
    """Create a new exclusive slot using source security, not token default owner."""
    check_deadline(deadline)
    source = local_regular_file(Path(source).absolute())
    if prefix not in (".music-tag-stage-", ".music-tag-restore-"):
        raise ValueError("Invalid staging purpose")
    if os.name != "nt":
        fd, name = tempfile.mkstemp(prefix=prefix, suffix=source.suffix, dir=source.parent)
        os.close(fd)
        return Path(name)
    import ctypes
    from ctypes import wintypes

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", wintypes.LPVOID), ("bInheritHandle", wintypes.BOOL)]

    descriptor = ctypes.create_string_buffer(windows_security_descriptor(source))
    attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), ctypes.cast(descriptor, wintypes.LPVOID), False)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(SecurityAttributes), wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    stage = source.parent / (prefix + uuid.uuid4().hex + source.suffix)
    # CREATE_NEW cannot overwrite a collision or an existing library file.
    handle = create("\\\\?\\" + str(stage.absolute()), 0xC0000000, 0, ctypes.byref(attributes), 1, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    if not close(handle):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        check_deadline(deadline)
    except TimeoutError:
        stage.unlink()
        raise
    return stage


def copy_for_commit(source, target, deadline=None):
    """Native copy retains ADS; host timeout must bound blocking OS operations."""
    check_deadline(deadline)
    expected = security_digest(source)
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True).CopyFileW
        api.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.BOOL]
        api.restype = wintypes.BOOL
        source_name = "\\\\?\\" + str(Path(source).absolute())
        target_name = "\\\\?\\" + str(Path(target).absolute())

        def _do_copy():
            if not api(source_name, target_name, False):
                raise ctypes.WinError(ctypes.get_last_error())

        retry_on_sharing_violation(_do_copy, deadline=deadline)
    else:
        shutil.copy2(source, target)
    check_deadline(deadline)
    if not (security_digest(target) == expected):
        raise ValueError('File ownership/DACL changed; do not commit')
    return expected


def save_json(path, data):
    import json

    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".receipt-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            json.dump(data, h, ensure_ascii=False, indent=2)
            h.flush()
            os.fsync(h.fileno())
        os.replace(name, path)
    finally:
        if Path(name).exists():
            Path(name).unlink()


@contextmanager
def library_lock(library_root):
    root = local_path(Path(library_root).absolute())
    lock = root / ".musicbee-dj-tag-writer.lock"
    token = uuid.uuid4().hex
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="ascii") as h:
            h.write(token)
            h.flush()
            os.fsync(h.fileno())
        yield
    finally:
        # No stale-lock deletion or guessing: only remove this exact ownership token.
        if (
            lock.is_file()
            and not lock.is_symlink()
            and lock.read_text(encoding="ascii") == token
        ):
            lock.unlink()


def header_end(path):
    path = Path(path)
    with path.open("rb") as source:
        magic = source.read(10)
        if path.suffix.lower() == ".mp3":
            if magic[:3] != b"ID3":
                return 0
            if not (all((x < 128 for x in magic[6:10]))):
                raise ValueError('Malformed ID3 size')
            size = sum(b << (7 * (3 - i)) for i, b in enumerate(magic[6:10]))
            return 10 + size + (10 if magic[3] == 4 and magic[5] & 16 else 0)
        if magic[:3] == b"ID3":
            if not (all((x < 128 for x in magic[6:10]))):
                raise ValueError('Malformed ID3 size')
            size = sum(b << (7 * (3 - i)) for i, b in enumerate(magic[6:10]))
            source.seek(10 + size + (10 if magic[3] == 4 and magic[5] & 16 else 0))
        else:
            source.seek(0)
        if not (source.read(4) == b'fLaC'):
            raise ValueError('Unsupported FLAC prefix')
        while True:
            block = source.read(4)
            if not (len(block) == 4):
                raise ValueError('Truncated FLAC header')
            source.seek(int.from_bytes(block[1:], "big"), 1)
            if not (source.tell() <= path.stat().st_size):
                raise ValueError('Invalid FLAC block size')
            if block[0] & 128:
                return source.tell()


def protected(audio):
    targets = {k.casefold() for k in FIELDS}
    if isinstance(audio.tags, ID3):
        return {
            k: repr(frame)
            for k, frame in audio.tags.items()
            if not (
                frame.FrameID in {"TMOO", "TCON"}
                or (frame.FrameID == "TXXX" and frame.desc.casefold() in targets)
            )
        }
    return {k: v for k, v in mapped(audio).items() if k not in targets}


def flac_blocks(path):
    kept = []
    with Path(path).open("rb") as source:
        magic = source.read(10)
        if magic[:3] == b"ID3":
            if not (all((x < 128 for x in magic[6:10]))):
                raise ValueError('Malformed ID3 size')
            size = sum(b << (7 * (3 - i)) for i, b in enumerate(magic[6:10]))
            source.seek(10 + size + (10 if magic[3] == 4 and magic[5] & 16 else 0))
        else:
            source.seek(0)
        if not (source.read(4) == b'fLaC'):
            raise ValueError('Metadata safety check failed')
        while True:
            h = source.read(4)
            if not (len(h) == 4):
                raise ValueError('Metadata safety check failed')
            payload = source.read(int.from_bytes(h[1:], "big"))
            if h[0] & 127 not in {1, 4}:
                kept.append((h[0] & 127, hashlib.sha256(payload).hexdigest()))
            if h[0] & 128:
                return kept


def mutate(path, changes):
    audio = mutagen.File(path)
    if not (audio is not None):
        raise ValueError('Metadata safety check failed')
    if isinstance(audio, FLAC):
        if audio.tags is None:
            audio.add_tags()
        for k, v in changes.items():
            audio[k] = [v]
        audio.save()
    elif isinstance(audio, MP3):
        if audio.tags is None:
            audio.add_tags()
        tags = audio.tags
        version = tags.version[1]
        if version not in {3, 4}:
            raise ValueError('Unsupported ID3 version; leave untouched')
        for k, v in changes.items():
            for key, frame in list(tags.items()):
                if (frame.FrameID == "TMOO" and k == "mood") or (
                    frame.FrameID == "TCON" and k == "Genre"
                ) or (
                    frame.FrameID == "TXXX" and frame.desc.casefold() == k.casefold()
                ):
                    del tags[key]
            if k == "mood" and version == 4:
                tags.add(TMOO(encoding=3, text=[v]))
            elif k == "Genre":
                tags.add(TCON(encoding=3, text=[v]))
            else:
                tags.add(TXXX(encoding=1 if version == 3 else 3, desc=k, text=[v]))
        tags.save(path, v1=1, v2_version=version, v23_sep=None)
    else:
        raise ValueError("Unsupported audio/tag format; leave untouched")


def public_source_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    host = parsed.hostname
    if (
        parsed.scheme not in {"http", "https"}
        or not host
        or parsed.username
        or parsed.password
    ):
        return False
    if host == "localhost" or host.endswith(
        (".local", ".localhost", ".internal", ".lan")
    ):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return "." in host


def valid_evidence_url(value):
    """Allow public web sources or controlled internal model-prior identifiers."""
    if not isinstance(value, str):
        return False
    if value in {"model://prior", "urn:model:prior"} or value.startswith("model://"):
        return True
    return public_source_url(value)


def read_results(result_path, inputs):
    return validate_results(read_json(result_path), inputs)


def validate_results(result, inputs):
    if not isinstance(result, dict) or set(result) != {"rows", "summary"}:
        raise ValueError("Research requires rows and summary")
    rows = result["rows"]
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Research rows must be objects")
    keys = [row.get("file") for row in rows]
    if not all(isinstance(key, str) for key in keys):
        raise ValueError("Invalid recording paths")
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate research rows")
    if set(keys) != set(inputs):
        raise ValueError("Research input/output mismatch")
    summary = result["summary"]
    if (not isinstance(summary, dict)
        or set(summary) != {"input_count", "researched_count", "limitations"}
        or type(summary["input_count"]) is not int or summary["input_count"] != len(inputs)
        or type(summary["researched_count"]) is not int
        or not 0 <= summary["researched_count"] <= len(inputs)
        or not isinstance(summary["limitations"], list)
        or not all(isinstance(note, str) for note in summary["limitations"])):
        raise ValueError("Invalid research summary counts/limitations")
    confidence_levels = {"high", "medium", "low"}
    required = {"file", "confidence", "unresolved", "evidence", *FIELDS}
    subjective = {"mood", "DJ_ENERGY", "DJ_SCENE", "Genre"}
    changes = {}
    for row in rows:
        if "Genre" not in row:
            row["Genre"] = ""
        field_confidence = row.get("field_confidence", {field: row["confidence"] for field in FIELDS})
        if "Genre" not in field_confidence:
            field_confidence["Genre"] = row.get("confidence", "low")
        if not required <= set(row) or set(row) - required - {"field_confidence"}:
            raise ValueError("Invalid research row schema")
        if row["confidence"] not in confidence_levels:
            raise ValueError("Invalid confidence")
        field_confidence = row.get("field_confidence", {field: row["confidence"] for field in FIELDS})
        if (not isinstance(field_confidence, dict) or set(field_confidence) != set(FIELDS)
            or any(value not in confidence_levels for value in field_confidence.values())):
            raise ValueError("Invalid field confidence")
        unresolved = row["unresolved"]
        if (not isinstance(unresolved, list) or not all(isinstance(field, str) for field in unresolved)
            or len(unresolved) != len(set(unresolved)) or not set(unresolved) <= set(FIELDS)):
            raise ValueError("Invalid unresolved fields")
        items = row["evidence"]
        if not isinstance(items, list) or len(items) > 2:
            raise ValueError("Evidence must be a bounded list")
        for item in items:
            if (not isinstance(item, dict) or set(item) != {"url", "supports", "note", "kind"}
                or not isinstance(item["url"], str) or not isinstance(item["note"], str)
                or item["kind"] not in {"source_fact", "inference"}
                or not isinstance(item["supports"], list)
                or not all(isinstance(field, str) for field in item["supports"])
                or not set(item["supports"]) <= set(FIELDS)):
                raise ValueError("Invalid evidence schema")
            if set(item["supports"]) & subjective and item["kind"] != "inference":
                raise ValueError("Subjective fields require inference evidence")
            if "Tempo" in item["supports"] and item["kind"] != "source_fact":
                raise ValueError("Tempo requires source_fact evidence")
            if "Tempo" in item["supports"] and not public_source_url(item["url"]):
                raise ValueError("Tempo requires a public source URL, not model prior")
        update = {}
        for field in FIELDS:
            value = row[field]
            if not isinstance(value, str) or (value and not acceptable(field, [value])):
                raise ValueError(f"Invalid {field} value")
            if (field not in inputs[row["file"]].get("requested_fields", FIELDS)
                or not incomplete(field, values(inputs[row["file"]]["tags"], field))
                or not value or value == "unknown" or field in unresolved
                or field_confidence[field] == "low"):
                continue
            if any(field in item["supports"] and valid_evidence_url(item["url"])
                   and item["note"].strip() for item in items):
                update[field] = value
        changes[row["file"]] = update
    return changes


def validate_review(result, inputs, review, result_sha256):
    changes = validate_results(result, inputs)
    if (not isinstance(review, dict) or set(review) != {"result_sha256", "run_reference", "decisions"}
        or review["result_sha256"] != result_sha256
        or not isinstance(review["run_reference"], str) or not review["run_reference"].strip()
        or not isinstance(review["decisions"], list)):
        raise ValueError("Review requires exact result SHA256 and a successful-run reference")
    expected = {(path, field) for path, update in changes.items() for field in update}
    seen, approved = set(), {path: {} for path in inputs}
    rows = {row["file"]: row for row in result["rows"]}
    for decision in review["decisions"]:
        if (not isinstance(decision, dict)
            or not {"file", "field", "decision", "note"} <= set(decision)
            or set(decision) - {"file", "field", "decision", "note", "url", "recording_match"}
            or not isinstance(decision["file"], str) or not isinstance(decision["field"], str)
            or decision["decision"] not in {"approve", "reject"}
            or not isinstance(decision["note"], str) or not decision["note"].strip()):
            raise ValueError("Invalid field review decision")
        pair = decision["file"], decision["field"]
        if pair not in expected or pair in seen:
            raise ValueError("Review field scope/duplicate mismatch")
        seen.add(pair)
        if decision["decision"] == "approve":
            url = decision.get("url")
            if (decision.get("recording_match") is not True or not valid_evidence_url(url)
                or not any(item["url"] == url and pair[1] in item["supports"]
                           for item in rows[pair[0]]["evidence"])):
                raise ValueError("Approval must bind a matching recording and result evidence URL")
            approved[pair[0]][pair[1]] = changes[pair[0]][pair[1]]
    if seen != expected:
        raise ValueError("Review must approve or reject every eligible field")
    return approved


def update_one(source, changes, baseline, backup_dir, library_root, deadline=None):
    check_deadline(deadline)
    source = local_regular_file(Path(source).absolute())
    root = local_path(Path(library_root).absolute()).resolve()
    if not (source.resolve().is_relative_to(root)):
        raise ValueError('Out-of-library write denied')
    if not (changes and set(changes) <= set(FIELDS) and all((acceptable(k, [v]) and v != 'unknown' for k, v in changes.items()))):
        raise ValueError('Metadata safety check failed')
    if not (all((incomplete(k, values(baseline['tags'], k)) for k in changes))):
        raise ValueError('Existing valid value overwrite denied')
    st = source.stat()
    if getattr(st, "st_file_attributes", 0) & 1:
        raise PermissionError(
            "Readonly file; changing file permissions is outside tag completion"
        )
    original_security = security_digest(source)
    if not ((st.st_size, st.st_mtime_ns) == (baseline['size'], baseline['mtime_ns'])):
        raise ValueError('Concurrent modification since scan')
    current = mutagen.File(source)
    if not (current is not None and mapped(current) == baseline['tags']):
        raise ValueError('Tag baseline drift')
    old_hash = digest(source, deadline=deadline)
    offset = header_end(source)
    start_offset, end_offset = payload_range(source)
    payload_len = end_offset - start_offset
    payload_hash = digest(source, start_offset, length=payload_len, deadline=deadline)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(exist_ok=True)
    local_path(backup_dir)
    key = hashlib.sha256(str(source).encode("utf-8")).hexdigest()
    header_path, receipt_path = (
        backup_dir / (key + ".header"),
        backup_dir / (key + ".json"),
    )
    if not (not header_path.exists() and (not receipt_path.exists())):
        raise ValueError('Existing recovery point; reconcile, do not overwrite')
    with source.open("rb") as h:
        header = h.read(offset)
    header_path.write_bytes(header)
    receipt = {
        "path": str(source),
        "before_sha256": old_hash,
        "payload_sha256": payload_hash,
        "header_sha256": hashlib.sha256(header).hexdigest(),
        "original_header_size": offset,
        "original_size": st.st_size,
        "original_mtime_ns": st.st_mtime_ns,
        "changes": changes,
        "status": "prepared",
    }
    save_json(receipt_path, receipt)
    stage = staging_file(source, deadline=deadline)
    try:
        copy_for_commit(source, stage, deadline=deadline)
        if not (mapped(mutagen.File(stage)) == baseline['tags']):
            raise ValueError('Tag drift during staging copy')
        mutate(stage, changes)
        after = mutagen.File(stage)
        if not (after is not None and protected(after) == protected(current)):
            raise ValueError('Unrelated metadata changed')
        for k, v in changes.items():
            if not (values(mapped(after), k) == [v]):
                raise ValueError(f'{k} readback mismatch')
        if isinstance(current, FLAC):
            if not (flac_blocks(source) == flac_blocks(stage)):
                raise ValueError('Non-comment FLAC metadata changed')
        stage_start, stage_end = payload_range(stage)
        if not (digest(stage, stage_start, length=stage_end - stage_start, deadline=deadline) == payload_hash):
            raise ValueError('Audio payload or trailing tags changed')
        if not (digest(source, deadline=deadline) == old_hash and source.stat().st_mtime_ns == st.st_mtime_ns):
            raise ValueError('Concurrent drift before commit')
        if not (security_digest(source) == original_security):
            raise ValueError('Concurrent file security change')
        if not (security_digest(stage) == original_security):
            raise ValueError('Staging file security changed')
        receipt["security_sha256"] = original_security
        receipt["after_sha256"] = digest(stage, deadline=deadline)
        save_json(receipt_path, receipt)
        check_deadline(deadline)
        retry_on_sharing_violation(lambda: os.replace(stage, source), deadline=deadline)
        receipt["status"] = "committed"
        save_json(receipt_path, receipt)
        if not (digest(source) == receipt['after_sha256']):
            raise ValueError('Post-commit hash mismatch')
        readback = mutagen.File(source)
        if not (readback is not None and protected(readback) == protected(current)):
            raise ValueError('Metadata safety check failed')
        if not (all((values(mapped(readback), k) == [v] for k, v in changes.items()))):
            raise ValueError('Post-commit tag readback mismatch')
        return receipt
    finally:
        if stage.exists():
            stage.unlink()


def restore(source, receipt_path, header_path, library_root):
    source = local_regular_file(Path(source).absolute())
    receipt = read_json(receipt_path)
    before_security = security_digest(source)
    if not (source.resolve().is_relative_to(local_path(Path(library_root).absolute()).resolve())):
        raise ValueError('Metadata safety check failed')
    if not (str(source) == receipt['path']):
        raise ValueError('Metadata safety check failed')
    if not (digest(source) == receipt['after_sha256']):
        raise ValueError('Post-write drift; do not overwrite')
    start_offset, end_offset = payload_range(source)
    if not (digest(source, start_offset, length=end_offset - start_offset) == receipt['payload_sha256']):
        raise ValueError('Metadata safety check failed')
    header = Path(header_path).read_bytes()
    if not (hashlib.sha256(header).hexdigest() == receipt['header_sha256']):
        raise ValueError('Metadata safety check failed')
    stage = staging_file(source, prefix=".music-tag-restore-")
    try:
        copy_for_commit(source, stage)
        # Opening with wb uses CREATE_ALWAYS on Windows and would discard ADS.
        with stage.open("r+b") as out, source.open("rb") as inp:
            out.seek(0)
            out.write(header)
            inp.seek(header_end(source))
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.truncate()
        if not (digest(stage) == receipt['before_sha256']):
            raise ValueError('Recovery checksum mismatch')
        shutil.copystat(source, stage)
        if not (digest(source) == receipt['after_sha256']):
            raise ValueError('Concurrent drift before restore')
        if not (security_digest(source) == before_security):
            raise ValueError('Concurrent file security change before restore')
        if not (security_digest(stage) == before_security):
            raise ValueError('Recovery stage file security changed')
        retry_on_sharing_violation(lambda: os.replace(stage, source))
        os.utime(source, ns=(source.stat().st_atime_ns, receipt["original_mtime_ns"]))
        receipt["status"] = "restored"
        save_json(receipt_path, receipt)
    finally:
        if stage.exists():
            stage.unlink()
