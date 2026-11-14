"""Explicit, preview-first external tool integration; no downloads or shell commands."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

SOURCE = 'https://github.com/loot/loot/blob/03f22e99f037c08778731319a6bae0276e7464a0/docs/app/usage/initialisation.rst'
MAX_EXECUTABLE_BYTES = 512 * 1024 * 1024


def inspect_executable(path, *, windows_binary=False):
    """Fingerprint an explicitly selected native binary, not an authenticity check."""
    path = Path(path).absolute()
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400:
        raise ValueError('executable must be a regular non-reparse file')
    if before.st_size > MAX_EXECUTABLE_BYTES:
        raise ValueError('executable exceeds fingerprint limit')
    if (windows_binary or os.name == 'nt') and path.suffix.lower() != '.exe':
        raise ValueError('Windows integration requires an exe, not a shell script')
    digest = hashlib.sha256()
    read = 0
    identity_fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or any(
                getattr(before, field) != getattr(opened, field) for field in identity_fields):
            raise ValueError('executable changed before fingerprinting')
        magic = stream.read(4)
        if not (magic.startswith(b'MZ') if windows_binary or os.name == 'nt' else magic == b'\x7fELF'):
            raise ValueError('unsupported native executable format')
        digest.update(magic)
        read += len(magic)
        while chunk := stream.read(65536):
            read += len(chunk)
            if read > MAX_EXECUTABLE_BYTES:
                raise ValueError('executable exceeds fingerprint limit')
            digest.update(chunk)
        observed = os.fstat(stream.fileno())
        # Windows lstat/fstat ctime meanings differ: compare within fstat only.
        if any(getattr(opened, field) != getattr(observed, field)
               for field in (*identity_fields, 'st_ctime_ns')):
            raise ValueError('executable changed during fingerprinting')
    after = path.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    if read != before.st_size or any(getattr(before, f) != getattr(after, f) for f in fields):
        raise ValueError('executable changed during fingerprinting')
    return path, digest.hexdigest()


def _launch(executable, tool, *, execute=False, expected_sha256=None, acknowledge_side_effects=False):
    windows_binary = tool == 'xedit-view'
    path, digest = inspect_executable(executable, windows_binary=windows_binary)
    if tool == 'loot':
        arguments = ['--game=Skyrim Special Edition']
        source = SOURCE
        warnings = ['LOOT may write settings/logs and perform configured network activity.',
                    'Existing LOOT instances may ignore these arguments and focus their window.',
                    'No auto-sort/apply is requested; subsequent GUI actions are outside this receipt.']
    elif tool == 'xedit-view':
        arguments = ['-sse', '-plugins', '-view', '-DontCache']
        source = 'https://github.com/TES5Edit/TES5Edit/blob/0f3f6fb2181783cad9c0cd4106ad0ff79ae7bb23/xEdit/xeInit.pas'
        warnings = ['Requests SSE plugin view mode with editing/saving disabled by upstream mode.',
                    'Reference caching is disabled, but settings/log writes may still occur.',
                    'No script, cleaning, master rewrite, FormID compaction or ESL flag change is requested.',
                    'Native Windows only; preview is available elsewhere, Wine is not configured.',
                    'Configured game discovery and GUI plugin selection still require native verification.']
    else:
        raise ValueError('unsupported tool')
    argv = [str(path), *arguments]
    report = {'schema_version': 1, 'scope': 'external-' + tool + '-launch', 'status': 'preview',
              'game_verified': False, 'tool_identity_verified': False, 'native_acceptance_verified': False,
              'operation_completed': False, 'process_started': False,
              'execution_platform_supported': not windows_binary or os.name == 'nt',
              'executable_sha256': digest, 'argv': argv, 'source': source,
              'warnings': warnings + ['A hash pins chosen bytes, not publisher authenticity. Stop concurrent executable changes.']}
    if not execute:
        return report
    if not report['execution_platform_supported']:
        raise ValueError('native Windows required for xEdit execution')
    if not acknowledge_side_effects:
        raise ValueError('execution requires acknowledgement of external tool side effects')
    if not isinstance(expected_sha256, str) or expected_sha256.lower() != digest:
        raise ValueError('execution requires the exact preview executable SHA-256')
    # Recheck immediately before process creation, but do not claim a hostile-race guarantee.
    if inspect_executable(path, windows_binary=windows_binary)[1] != digest:
        raise ValueError('executable changed since preview')
    process = subprocess.Popen(argv, shell=False, cwd=str(path.parent),
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    report.update(status='process-started-not-verified', process_started=True, pid=process.pid)
    return report


def launch_loot(executable, **options):
    return _launch(executable, 'loot', **options)


def launch_xedit_view(executable, **options):
    return _launch(executable, 'xedit-view', **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tool', choices=['loot', 'xedit-view'])
    parser.add_argument('executable', help='explicit installed official native executable; never downloaded')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--acknowledge-tool-side-effects', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = _launch(args.executable, args.tool, execute=args.execute,
                             expected_sha256=args.expected_sha256,
                             acknowledge_side_effects=args.acknowledge_tool_side_effects)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'tool-not-launched', 'error_type': type(exc).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
