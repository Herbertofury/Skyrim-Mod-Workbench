"""Explicit create-only report snapshots and bounded integrity verification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys

MAX_BYTES = 32 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8')


def envelope(report):
    if not isinstance(report, dict) or type(report.get('schema_version')) is not int or report.get('schema_version') != 1 or report.get('game_verified') is not False:
        raise ValueError('expected non-native workbench report')
    payload = canonical(report)
    result = {'evidence_version': 1, 'algorithm': 'sha256',
              'report_sha256': hashlib.sha256(payload).hexdigest(), 'report': report}
    encoded = canonical(result) + b'\n'
    if len(encoded) > MAX_BYTES:
        raise ValueError('evidence exceeds byte limit')
    return encoded


def save_report(report, destination):
    """Publish a new file atomically, never replace an existing receipt or backup."""
    encoded = envelope(report)
    target = Path(destination)
    if target.is_symlink() or target.exists():
        raise FileExistsError('evidence destination exists')
    # Same-directory temporary file permits atomic hard-link publication.
    fd, temporary = tempfile.mkstemp(prefix='.workbench-evidence-', dir=target.parent)
    temporary = Path(temporary)
    published = False
    temporary_removed = True
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # link is create-only even when another writer wins after the initial check.
        os.link(temporary, target)
        published = True
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            if not published:
                raise
            temporary_removed = False
    receipt = {'published': published, 'file_fsynced': True, 'temporary_removed': temporary_removed,
               'directory_fsync': 'not-supported-on-this-platform', 'bytes': len(encoded)}
    if os.name == 'posix':
        directory_fd = None
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
            os.fsync(directory_fd)
            receipt['directory_fsync'] = 'confirmed'
        except OSError:
            # File exists: do not report failure as though retrying could be safe.
            receipt['directory_fsync'] = 'unconfirmed'
        finally:
            if directory_fd is not None:
                os.close(directory_fd)
    return receipt


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def load_report(source):
    with open(source, 'rb') as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('evidence exceeds byte limit')
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object)
    if not isinstance(value, dict) or set(value) != {'evidence_version', 'algorithm', 'report_sha256', 'report'}:
        raise ValueError('invalid evidence envelope')
    if type(value['evidence_version']) is not int or value['evidence_version'] != 1 or value['algorithm'] != 'sha256':
        raise ValueError('unsupported evidence version or algorithm')
    # Validate the report envelope contract as well as its digest.
    envelope(value['report'])
    actual = hashlib.sha256(canonical(value['report'])).hexdigest()
    if value['report_sha256'] != actual:
        raise ValueError('evidence checksum mismatch')
    return value['report']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', help='existing evidence snapshot to verify; no writes')
    args = parser.parse_args(argv)
    try:
        report = load_report(args.snapshot)
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({'status': 'invalid-evidence', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps({'status': 'integrity-verified', 'historical': True,
                      'authenticity_verified': False, 'current_files_verified': False,
                      'report': report}, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
