"""Explicit create-only report snapshots and bounded integrity verification."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import sys
import stat

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
                try:
                    os.close(directory_fd)
                except OSError:
                    # Publication already happened; never report this as unsaved.
                    # Do not retry close: the descriptor may already be released.
                    receipt['directory_fsync'] = 'unconfirmed'
    return receipt



def save_cli_report(report, destination):
    """Emit a save receipt on stderr; return whether CLI should warn with exit 2."""
    try:
        receipt = save_report(report, destination)
        print(json.dumps({'evidence_save': receipt}), file=sys.stderr)
        return receipt['directory_fsync'] == 'unconfirmed' or not receipt['temporary_removed']
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({'status': 'evidence-not-saved', 'error_type': type(exc).__name__}), file=sys.stderr)
        return True


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def load_report(source):
    # A byte cap cannot bound waiting for a FIFO writer or an infinite device.
    # Preserve ordinary file/symlink-to-file inputs, but reject special objects.
    if not stat.S_ISREG(Path(source).stat().st_mode):
        raise ValueError('evidence source must be a regular file')
    def bounded_open(path, flags):
        # Also avoid blocking if a POSIX path is swapped to a FIFO after stat.
        return os.open(path, flags | getattr(os, 'O_NONBLOCK', 0))
    with open(source, 'rb', opener=bounded_open) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('evidence source must be a regular file')
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
    parser.add_argument('--html', action='store_true', help='view verified historical evidence as offline HTML; no rescan')
    parser.add_argument('snapshot', help='existing evidence snapshot to verify; no writes')
    args = parser.parse_args(argv)
    try:
        report = load_report(args.snapshot)
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({'status': 'invalid-evidence', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    if args.html:
        from report_html import render_report
        try:
            html = render_report(report, historical=True)
        except (KeyError, TypeError, ValueError) as exc:
            print(json.dumps({'status': 'unsupported-report-view', 'integrity_verified': True,
                              'error_type': type(exc).__name__}), file=sys.stderr)
            return 2
        print(html, end='')
        return 0
    print(json.dumps({'status': 'integrity-verified', 'historical': True,
                      'authenticity_verified': False, 'current_files_verified': False,
                      'report': report}, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
