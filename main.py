# coding=utf-8
r"""
Walking-duck taskbar mover that plays a REAL audio file (your duck "quack")
on every slot it steps across the Windows taskbar.
Provide the sound file in any of these ways:
  * put a file named  quack.wav  next to this script (auto-loaded), or
  * pass a path:   python duck_taskbar_mover_audiofile.py  C:\sounds\quack.mp3
  * click "Choose duck sound..." in the window.
Audio playback uses PyQt5's QtMultimedia:
  * .wav  -> a small pool of QSoundEffect objects (low latency; consecutive
            quacks overlap instead of being cut off), played round-robin.
  * other formats (.mp3, .ogg, .m4a, ...) -> QMediaPlayer (uses the platform
            codecs; on Windows that covers MP3/WMA/etc.).
================================  REQUIREMENTS  ==============================
1) Windows 10, build <= 19041 (May 2020 Update). TTLib 5.9 does NOT support
   newer Win10 builds or Windows 11 (it errors and may crash explorer.exe).
   For Windows 11 use the Windhawk "Taskbar reorder within/between groups" mod.
2) 64-bit Python (must match explorer.exe bitness).
3) TTLib64.dll next to this script. Get TTLib.zip from
   https://ramensoftware.com/7-taskbar-tweaking-library (free, non-commercial).
4) pip install PyQt5   (QtMultimedia ships with it)
Run:  python mainwindow.py [optional_sound_file]
=============================================================================
"""
from os.path import dirname
from sys import path, platform

if dirname(__file__) not in path:
    path.append(dirname(__file__))

try:
    from .walkingduck import SetCurrentProcessExplicitAppUserModelID
    from .mainwindow import MainWindow
except:
    from walkingduck import SetCurrentProcessExplicitAppUserModelID
    from mainwindow import MainWindow

if __name__ == '__main__':
    from ManyQt.QtWidgets import QApplication
    from sys import argv, exit

    if platform == 'win32':
        try:
            SetCurrentProcessExplicitAppUserModelID('Example.QuackingDuckTaskbarMover')
        except Exception:
            pass

    a = QApplication(argv)  # type: QApplication
    w = MainWindow(argv[1] if len(argv) > 1 else None)  # type: MainWindow
    w.show()
    exit(a.exec_())
