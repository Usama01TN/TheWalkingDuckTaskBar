#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
builder.py
============
Interactive/CLI builder that packages TheWalkingDuckTaskBar project
(main.py + mainwindow.py + walkingduck.py + __init__.py) into a single,
compressed, standalone Windows .exe using either PyInstaller or Nuitka.

TheWalkingDuckTaskBar is a PyQt5 (via the ManyQt compatibility layer) GUI toy
that waddles the window's taskbar button across the real Windows taskbar and
quacks on every step. Because it is a GUI app -- not a console tool -- it is
built WINDOWED (no console) by DEFAULT. Pass --console only if you want a
visible console window for debugging.

Must be run on WINDOWS with a Python interpreter matching the target
architecture (building a Windows exe on Linux/macOS is not supported by
either tool in --onefile mode). The interpreter must be 64-bit so the bundled
TTLib64.dll matches explorer.exe's bitness.

Usage:
-----
Interactive (asks which backend to use):
    python builder.py
Non-interactive:
    python builder.py --tool pyinstaller
    python builder.py --tool nuitka --console
    python builder.py --tool nuitka --upx --icon duck.ico

Options:
-------
    --tool {pyinstaller,nuitka}   Skip the interactive prompt.
    --entry PATH                  Entry script (default: main.py).
    --name NAME                   Output exe base name
                                   (default: TheWalkingDuckTaskBar).
    --source-dir PATH             Folder containing the project .py files
                                   (default: same folder as this script).
    --dist-dir PATH               Where the final exe is placed (default: ./dist).
    --icon PATH                   Optional .ico file for the exe.
    --ttlib PATH                  Path to TTLib64.dll to bundle into the exe.
                                   Auto-detected in --source-dir if omitted.
    --sound PATH                  Path to a default quack sound (e.g. quack.mp3
                                   or quack.wav) to bundle. Auto-detected in
                                   --source-dir if omitted.
    --console                     Build a console app (useful for debugging:
                                   Qt warnings/tracebacks show in a terminal).
    --no-console / --windowed     Build a GUI/no-console app (DEFAULT). This is
                                   the normal mode for this GUI toy.
    --no-upx                      Disable UPX binary compression even if available.
    --skip-install                Don't auto pip-install the build backend or
                                   the runtime deps (PyQt5 / ManyQt).
    --yes / -y                    Don't ask for confirmation before building.

What it does:
------------
1. Verifies you're on Windows and that all project files are present.
2. Installs the runtime deps (PyQt5, ManyQt) and the chosen backend
   (PyInstaller or Nuitka) via pip if missing.
3. Downloads/locates UPX for extra compression when available (optional,
   never a hard failure -- both tools work fine without it).
4. Bundles TTLib64.dll (and the default quack sound, if found) INTO the
   onefile exe so the duck can move the taskbar and quack with no loose files.
5. Runs a --onefile build tuned for small size:
     - PyInstaller: --onefile --strip --upx-dir=... --exclude common
       unneeded stdlib/test modules, --windowed by default (--console only
       when --console is passed), QtMultimedia + sibling modules pulled in
       as hidden imports.
     - Nuitka: --onefile --lto=yes --standalone --enable-plugin=pyqt5,
       windowed console mode by default (a real console only when --console
       is passed), --remove-output, data files included.
6. Copies the final .exe into --dist-dir and prints its size.

Notes on TTLib / size / optimization:
-------------------------------------
* TTLib64.dll (the 7+ Taskbar Tweaking Library from ramensoftware.com) is a
  hard runtime requirement -- walkingduck.py loads it from next to the
  executable via ctypes. This builder bundles it INTO the onefile; at runtime
  PyInstaller/Nuitka unpack the payload to a temp dir and __file__ resolves
  there, so the DLL is found. TTLib is free for NON-COMMERCIAL use only --
  check its license before redistributing an exe that embeds it.
* TTLib 5.9 only supports Windows 10 build <= 19041. The exe will still build
  on newer Windows, but LoadIntoExplorer will fail at runtime there.
* Bundle a 64-bit TTLib64.dll only -- it must match explorer.exe (always
  64-bit on modern Windows). Build with 64-bit Python accordingly.
* UPX (https://upx.github.io/) is optional but often shrinks the final exe
  by 40-60%% with no runtime cost beyond a slightly slower first launch
  (self-decompression). Point --upx-dir at it, or let this script try to
  find `upx`/`upx.exe` on PATH automatically.
"""
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from os.path import dirname, abspath, join, getsize, isfile
from os import getcwd, makedirs, name, pathsep
from sys import executable, exit, platform
from sysconfig import get_platform
from pip import _internal
from shutil import move

try:
    from shutil import which
except:
    from os import pathsep as _pathsep, environ, access, X_OK
    from os.path import split


    def which(filename):
        """
        Locate an executable on PATH.
        :param filename: str | unicode
        :return: str | unicode | None
        """

        def isExecutable(pth):
            """
            :param pth: str | unicode
            :return: bool
            """
            return isfile(pth) and access(pth, X_OK)

        path, _ = split(filename)
        if path:
            if isExecutable(filename):
                return filename
        else:
            for directory in environ.get('PATH', '').split(_pathsep):
                fullPath = join(directory, filename)
                if isExecutable(fullPath):
                    return fullPath
        exts = environ.get('PATHEXT', '').split(_pathsep)
        for directory in environ.get('PATH', '').split(_pathsep):
            for ext in [''] + exts:
                fullPath = join(directory, filename + ext)
                if isfile(fullPath) and access(fullPath, X_OK):
                    return fullPath
        return None

try:
    from subprocess import run
except:
    from subprocess import Popen, call, PIPE


    class _CompletedProcess(object):
        """
        Minimal subprocess.CompletedProcess shim.
        """

        def __init__(self, args, returncode, stdout=None, stderr=None):
            self.args = args
            self.returncode = returncode
            self.stdout = stdout or ''
            self.stderr = stderr or ''


    def run(cmd, cwd=None, env=None, capture_output=False, text=True, check=False):
        """
        Python shim for subprocess.run(capture_output=..., check=...).
        """
        if capture_output:
            proc = Popen(cmd, cwd=cwd, env=env, stdout=PIPE, stderr=PIPE)
            stdoutBytes, stderrBytes = proc.communicate()
            if text:
                stdout = stdoutBytes.decode('utf-8', errors='replace')
                stderr = stderrBytes.decode('utf-8', errors='replace')
            else:
                stdout, stderr = stdoutBytes, stderrBytes
            result = _CompletedProcess(cmd, proc.returncode, stdout, stderr)
        else:
            result = _CompletedProcess(cmd, call(cmd, cwd=cwd, env=env))
        if check and result.returncode != 0:
            raise SystemExit('Command {!r} failed with exit code {}.'.format(cmd, result.returncode))
        return result

# The Python source files that make up TheWalkingDuckTaskBar.
REQUIRED_FILES = ['main.py', 'mainwindow.py', 'walkingduck.py', '__init__.py']
# The taskbar-tweaking DLL the app loads at runtime. Bundled if present.
TTLIB_DLL = 'TTLib64.dll'
# Default quack sounds looked for (in order) when --sound is not given.
DEFAULT_SOUNDS = ['quack.mp3', 'quack.wav']
# Heavy stdlib modules never needed by this project -- excluding them from
# PyInstaller's analysis trims real size off the bundle.
PYINSTALLER_EXCLUDES = ['tkinter', 'unittest', 'pydoc', 'doctest', 'test', 'lib2to3', 'curses', 'idlelib', 'turtledemo']
# Runtime dependencies that must be importable so the freezer can bundle them.
RUNTIME_DEPS = ['PyQt5', 'ManyQt']


def die(msg, code=1):
    """
    :param msg: str | unicode
    :param code: int
    :return:
    """
    print('ERROR: {}'.format(msg))
    exit(code)


def haveModule(mod):
    """
    :param mod: str | unicode
    :return: bool
    """
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def pipInstall(pkgs, skip_install):
    missing = [p for p in pkgs if not haveModule(p.split('==')[0].replace('-', '_'))]
    if not missing:
        return
    if skip_install:
        die('Missing required package(s) {} and --skip-install was set.'.format(missing))
    _internal.main(['install', '--upgrade'] + missing)


def findUpx():
    """
    :return: str | unicode | None
    """
    for candidate in ('upx', 'upx.exe'):
        path = which(candidate)
        if path:
            return dirname(path)
    return None


def checkWindows():
    """
    :return:
    """
    if name != 'nt' and platform != 'win32':
        print(
            'WARNING: this does not look like Windows (os.name={!r}, '
            'sys.platform={!r}). PyInstaller/Nuitka --onefile can only '
            'produce a native Windows .exe when actually run ON Windows '
            '(no cross-compiling from Linux/macOS). The build below will '
            'very likely fail.'.format(name, platform))


def verifySources(source_dir):
    """
    :param source_dir: str | unicode
    :return:
    """
    missing = [f for f in REQUIRED_FILES if not isfile(join(source_dir, f))]
    if missing:
        die('Missing project file(s) in {}: {}'.format(source_dir, ', '.join(missing)))


def resolveTTLib(args):
    """
    Return the path to the TTLib64.dll to bundle, or None if not available.
    :param args: Namespace
    :return: str | unicode | None
    """
    if args.ttlib:
        if not isfile(args.ttlib):
            die('--ttlib path does not exist: {}'.format(args.ttlib))
        return abspath(args.ttlib)
    candidate = join(args.source_dir, TTLIB_DLL)
    if isfile(candidate):
        return candidate
    print(
        'WARNING: {0} was not found in the source dir and --ttlib was not\n'
        '         given, so it will NOT be bundled. The exe will fail to move\n'
        '         the taskbar until {0} sits next to it. Download TTLib.zip\n'
        '         from ramensoftware.com to get it.'.format(TTLIB_DLL))
    return None


def resolveSound(args):
    """
    Return the path to a default quack sound to bundle, or None.
    :param args: Namespace
    :return: str | unicode | None
    """
    if args.sound:
        if not isfile(args.sound):
            die('--sound path does not exist: {}'.format(args.sound))
        return abspath(args.sound)
    for snd in DEFAULT_SOUNDS:
        candidate = join(args.source_dir, snd)
        if isfile(candidate):
            return candidate
    print(
        'NOTE: no default quack sound (quack.mp3 / quack.wav) found to bundle.\n'
        '      The app will start silent; users can still pick a sound with\n'
        '      "Choose duck sound..." at runtime.')
    return None


# ---------------------------------------------------------------------------
# Install the runtime packages the freezer needs to see
# ---------------------------------------------------------------------------
def installPackages(args):
    pipInstall(RUNTIME_DEPS, args.skip_install)


# ---------------------------------------------------------------------------
# Backend: PyInstaller
# ---------------------------------------------------------------------------
def buildPyinstaller(args, upx_dir, ttlib_path, sound_path):
    pipInstall(['pyinstaller'], args.skip_install)
    cmd = [
        executable, '-m', 'PyInstaller',
        '--onefile',
        '--noconfirm',
        '--clean',
        '--name', args.name,
        '--distpath', args.dist_dir,
        '--workpath', join(args.dist_dir, '_build'),
        '--specpath', join(args.dist_dir, '_build')]
    if args.no_console:
        cmd.append('--windowed')  # GUI toy: no console window (DEFAULT)
    else:
        cmd.append('--console')  # opt-in: show Qt warnings/tracebacks in a terminal
    if not args.no_upx and upx_dir:
        cmd += ['--upx-dir', upx_dir]
    elif not args.no_upx:
        print('NOTE: UPX not found on PATH -- building without it. '
              'Install UPX and re-run for a smaller exe, or pass --no-upx '
              'to silence this note.')
    for m in PYINSTALLER_EXCLUDES:
        cmd += ['--exclude-module', m]
    if args.icon:
        cmd += ['--icon', args.icon]
    # Bundle the taskbar DLL as a binary and the default sound as data.
    # On Windows PyInstaller uses ';' between SRC and DEST.
    if ttlib_path:
        cmd += ['--add-binary', '{}{}.'.format(ttlib_path, pathsep)]
    if sound_path:
        cmd += ['--add-data', '{}{}.'.format(sound_path, pathsep)]
    # Pull in QtMultimedia and the sibling modules explicitly so PyInstaller's
    # static analysis is guaranteed to find them even though the try/except
    # import fallbacks in the project can confuse its import scanner.
    for extra in ('PyQt5.QtMultimedia', 'walkingduck', 'mainwindow'):
        cmd += ['--hidden-import', extra]
    cmd.append(args.entry)
    print('\n$ {}'.format(' '.join(cmd)))
    run(cmd, check=True, cwd=args.source_dir)
    return join(args.dist_dir, args.name + '.exe')


# ---------------------------------------------------------------------------
# Backend: Nuitka
# ---------------------------------------------------------------------------
def buildNuitka(args, upx_dir, ttlib_path, sound_path):
    pipInstall(['nuitka', 'ordered-set', 'zstandard'], args.skip_install)
    out_name = args.name + '.exe'
    cmd = [executable, '-m', 'nuitka', '--onefile', '--lto=yes', '--assume-yes-for-downloads', '--remove-output',
           '--enable-plugin=pyqt5',
           '--output-dir=' + args.dist_dir, '--output-filename=' + out_name]
    if args.no_console:
        cmd.append('--windows-console-mode=disable')  # GUI toy: no console (DEFAULT)
    # else: leave Nuitka's default (a real, visible console) for debugging.
    if not args.no_upx and upx_dir:
        cmd.append('--onefile-tempdir-spec={TEMP}/duck_%PID%')
        # Nuitka's onefile mode already compresses its payload; UPX on top of
        # the bootstrap stub is applied automatically when `upx` is on PATH.
    if args.icon:
        cmd.append('--windows-icon-from-ico=' + args.icon)
    # Include the runtime data files INTO the onefile.
    if ttlib_path:
        cmd.append('--include-data-files={}={}'.format(ttlib_path, TTLIB_DLL))
    if sound_path:
        from os.path import basename
        cmd.append('--include-data-files={}={}'.format(sound_path, basename(sound_path)))
    cmd.append(args.entry)
    print('\n$ {}'.format(' '.join(cmd)))
    run(cmd, check=True, cwd=args.source_dir)
    built = join(args.dist_dir, out_name)
    if not isfile(built):
        # Older Nuitka versions place it next to the entry script instead.
        alt = join(args.source_dir, out_name)
        if isfile(alt):
            makedirs(args.dist_dir, exist_ok=True)
            move(alt, built)
    return built


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def parseArgs(argv):
    p = ArgumentParser(description=__doc__, formatter_class=RawDescriptionHelpFormatter)
    p.add_argument('--tool', choices=['pyinstaller', 'nuitka'],
                   help="Build backend. If omitted, you'll be asked interactively.")
    p.add_argument('--entry', default='main.py', help='Entry script.')
    p.add_argument('--name', default='TheWalkingDuckTaskBar', help='Output exe base name.')
    p.add_argument('--source-dir', default=dirname(abspath(__file__)),
                   help="Folder containing the project's .py files.")
    p.add_argument('--dist-dir', default=join(getcwd(), 'dist'),
                   help='Output folder for the built exe.')
    p.add_argument('--icon', default=join(dirname(__file__), 'duck.ico'), help='Optional .ico file.')
    p.add_argument('--ttlib', default=None,
                   help='Path to TTLib64.dll to bundle (auto-detected in --source-dir).')
    p.add_argument('--sound', default=None,
                   help='Path to a default quack sound to bundle (auto-detected in --source-dir).')
    # This is a GUI app: it should be WINDOWED (no console) by default. Pass
    # --console only to get a visible console for debugging Qt output.
    console = p.add_mutually_exclusive_group()
    console.add_argument('--no-console', '--windowed', dest='no_console', action='store_true',
                         help='Build a GUI/no-console app (DEFAULT).')
    console.add_argument('--console', dest='no_console', action='store_false',
                         help='Build a console app to see Qt warnings/tracebacks in a terminal.')
    p.set_defaults(no_console=True)
    p.add_argument('--no-upx', action='store_true', help='Disable UPX compression.')
    p.add_argument('--skip-install', action='store_true',
                   help="Don't auto pip-install the build backend or runtime deps.")
    p.add_argument('-y', '--yes', action='store_true',
                   help="Don't ask for confirmation before building.")
    return p.parse_args(argv)


def askTool():
    """
    :return:
    """
    print('Which backend do you want to build with?')
    print('  1) PyInstaller  -- simpler, very widely used, good UPX support')
    print('  2) Nuitka       -- compiles to C first, usually faster & smaller output')
    while True:
        choice = input('Enter 1 or 2: ').strip()
        if choice == '1':
            return 'pyinstaller'
        if choice == '2':
            return 'nuitka'
        print('Please enter 1 or 2.')


def main(argv=None):
    args = parseArgs(argv)
    checkWindows()
    args.source_dir = abspath(args.source_dir)
    args.dist_dir = abspath(args.dist_dir)
    verifySources(args.source_dir)
    tool = args.tool or askTool()
    upx_dir = None if args.no_upx else findUpx()
    ttlib_path = resolveTTLib(args)
    sound_path = resolveSound(args)
    print('\nBuild plan:')
    print('  tool         : {}'.format(tool))
    print('  entry        : {}'.format(join(args.source_dir, args.entry)))
    print('  output name  : {}.exe'.format(args.name))
    print('  dist dir     : {}'.format(args.dist_dir))
    print('  window mode  : {}'.format('GUI / no console (default)' if args.no_console else 'console (debug)'))
    print('  TTLib64.dll  : {}'.format(ttlib_path or 'NOT bundled (must sit next to the exe)'))
    print('  quack sound  : {}'.format(sound_path or 'none bundled (choose at runtime)'))
    print('  UPX          : {}'.format(upx_dir or ('disabled' if args.no_upx else 'not found')))
    print('  python       : {} ({})'.format(executable, get_platform()))
    if not args.yes:
        reply = input('\nProceed with build? [y/N] ').strip().lower()
        if reply not in ('y', 'yes'):
            print('Aborted.')
            return 0
    print('Installing the packages...')
    installPackages(args)
    makedirs(args.dist_dir, exist_ok=True)
    if tool == 'pyinstaller':
        exe_path = buildPyinstaller(args, upx_dir, ttlib_path, sound_path)
    else:
        exe_path = buildNuitka(args, upx_dir, ttlib_path, sound_path)
    if isfile(exe_path):
        size_mb = getsize(exe_path) / (1024 * 1024)
        print('\nBuild finished: {}  ({:.1f} MB)'.format(exe_path, size_mb))
        return 0
    die("Build appears to have completed but the expected exe was not found at {}. Check the tool's output.".format(
        exe_path))
    return None


if __name__ == '__main__':
    exit(main())
