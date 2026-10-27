"""Install a pinned, checksum-verified portable g++ in this workspace (Windows)."""
import hashlib
from pathlib import Path, PurePosixPath
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / '.build' / 'toolchain'
URL = 'https://github.com/brechtsanders/winlibs_mingw/releases/download/13.3.0posix-11.0.1-ucrt-r1/winlibs-x86_64-posix-seh-gcc-13.3.0-mingw-w64ucrt-11.0.1-r1.zip'
SHA256 = '6c90485da4d9966683a83a1e5f3a0b1084d2a5ba2e57e8b27c0634afe3983776'


def main():
    if sys.platform != 'win32':
        print('This optional bootstrap is for Windows; install GCC 11+ with your platform package manager.')
        return 2
    DESTINATION.mkdir(parents=True, exist_ok=True)
    archive = DESTINATION / 'winlibs.zip'
    if not archive.is_file():
        print('Downloading the pinned WinLibs GCC 13.3 archive (217 MiB)...', flush=True)
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if digest != SHA256:
        print(f'Checksum mismatch for {archive}; expected {SHA256}, got {digest}', file=sys.stderr)
        return 1
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'mingw64' or '\\' in member.filename:
                raise ValueError(f'Unsafe archive member: {member.filename}')
        bundle.extractall(DESTINATION)
    print('Verified GCC is ready at ' + str(DESTINATION / 'mingw64' / 'bin' / 'g++.exe'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
