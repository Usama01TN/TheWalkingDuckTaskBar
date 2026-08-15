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
from ManyQt.QtGui import QPixmap, QIcon, QPainter, QColor, QBrush, QPen, QPolygon
from ManyQt.QtCore import Qt, QPoint, QUrl
from ctypes import c_void_p, WinDLL, c_int, c_uint32, POINTER, windll, c_size_t, c_wchar_p, sizeof, byref, \
    create_unicode_buffer
from os.path import exists, abspath, dirname, join
from sys import platform

try:
    from ManyQt.QtMultimedia import QSoundEffect, QMediaPlayer, QMediaContent

    HAVE_MULTIMEDIA = True  # type: bool
except Exception:
    HAVE_MULTIMEDIA = False  # type: bool

MAX_APPID_LENGTH = 260  # type: int # MAX_PATH, per TTLib.h
SetCurrentProcessExplicitAppUserModelID = windll.shell32.SetCurrentProcessExplicitAppUserModelID


# ---------------------------------------------------------------------------
# Audio: load and play a real sound file.
# ---------------------------------------------------------------------------
class QuackPlayer(object):
    """
    Plays a loaded audio file. WAV -> QSoundEffect pool; else -> QMediaPlayer.
    """

    def __init__(self, poolSize=4):
        """
        :param poolSize: int
        """
        self.path = None
        self.__m_isWav = False  # type: bool
        self.__m_effects = []
        self.__m_player = None  # type: QMediaPlayer | None
        self.__m_rr = 0  # type: int
        self.__m_poolSize = poolSize  # type: int

    @staticmethod
    def available():
        """
        :return: bool
        """
        return HAVE_MULTIMEDIA

    def load(self, path):
        """
        :param path: str | unicode
        :return: bool
        """
        if not HAVE_MULTIMEDIA or not path or not exists(path):
            return False
        path = abspath(path)  # type: str
        url = QUrl.fromLocalFile(path)  # type: QUrl
        self.__m_effects = []
        self.__m_player = None  # type: QMediaPlayer | None
        self.__m_isWav = path.lower().endswith('.wav')  # type: bool
        if self.__m_isWav:
            for _ in range(self.__m_poolSize):
                eff = QSoundEffect()  # type: QSoundEffect
                eff.setSource(url)
                eff.setVolume(0.9)
                self.__m_effects.append(eff)
        else:
            self.__m_player = QMediaPlayer()  # type: QMediaPlayer
            self.__m_player.setMedia(QMediaContent(url))
            self.__m_player.setVolume(90)
        self.path = path  # type: str
        return True

    def play(self):
        """
        :return:
        """
        if self.__m_isWav and self.__m_effects:
            # Round-robin across instances so rapid quacks can overlap.
            eff = self.__m_effects[self.__m_rr % len(self.__m_effects)]
            self.__m_rr += 1  # type: int
            eff.play()
        elif self.__m_player is not None:
            self.__m_player.stop()
            self.__m_player.setPosition(0)
            self.__m_player.play()

    def stop(self):
        """
        :return:
        """
        for eff in self.__m_effects:
            eff.stop()
        if self.__m_player is not None:
            self.__m_player.stop()


# ---------------------------------------------------------------------------
# Duck artwork (pure Qt -- no image files needed).
# ---------------------------------------------------------------------------
BODY = QColor('#ffd23f')  # type: QColor
BEAK = QColor('#ff7a00')  # type: QColor
LEG = QColor('#ef6c00')  # type: QColor
WING = QColor('#e0a800')  # type: QColor
EYE = QColor('#222222')  # type: QColor


def makeDuckIcon(phase, facingRight=True, idle=False, size=64):
    """
    Return a QIcon of a cartoon duck. `phase` 0..3 is the walk-cycle frame.
    :param phase: int
    :param facingRight: bool
    :param idle: bool
    :param size: int
    :return: QIcon
    """
    pix = QPixmap(size, size)  # type: QPixmap
    pix.fill(Qt.transparent)
    p = QPainter(pix)  # type: QPainter
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size / 64.0, size / 64.0)
    if not facingRight:
        p.translate(64, 0)
        p.scale(-1, 1)
    if idle:
        legADx = legBDx = 0  # type: int
        bodyDy = 0  # type: int
    else:
        legADx = (6, 0, -6, 0)[phase]  # type: int
        legBDx = (-6, 0, 6, 0)[phase]  # type: int
        bodyDy = (0, -2, 0, -2)[phase]  # type: int
    p.setPen(QPen(LEG, 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(30, 44 + bodyDy, 30 + legADx, 56)
    p.drawLine(34, 44 + bodyDy, 34 + legBDx, 56)
    p.drawLine(30 + legADx, 56, 30 + legADx + 6, 57)
    p.drawLine(34 + legBDx, 56, 34 + legBDx + 6, 57)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(BODY))
    p.drawEllipse(12, 26 + bodyDy, 34, 22)
    p.drawPolygon(QPolygon([QPoint(14, 30 + bodyDy), QPoint(6, 28 + bodyDy), QPoint(15, 38 + bodyDy)]))
    p.drawEllipse(35, 12 + bodyDy, 18, 18)
    p.setBrush(QBrush(BEAK))
    p.drawPolygon(QPolygon([QPoint(52, 18 + bodyDy), QPoint(63, 21 + bodyDy), QPoint(52, 25 + bodyDy)]))
    p.setBrush(QBrush(WING))
    p.drawEllipse(20, 31 + bodyDy, 16, 9)
    p.setBrush(QBrush(EYE))
    p.drawEllipse(46, 17 + bodyDy, 3, 3)
    p.end()
    return QIcon(pix)


# ---------------------------------------------------------------------------
# TTLib wrapper
# ---------------------------------------------------------------------------
class TTLibError(Exception):
    """
    TTLibError Exception class.
    """


class TaskbarMover(object):
    """
    Thin ctypes wrapper around the parts of TTLib we need.
    """
    GROUPTYPE = {0: 'unknown', 1: 'normal', 2: 'pinned', 3: 'combined', 4: 'temporary'}  # type: dict[int, str]

    def __init__(self):
        if platform != 'win32':
            raise TTLibError('This feature only works on Windows.')
        dllName = 'TTLib{}.dll'.format(64 if sizeof(c_void_p) == 8 else 32)  # type: str
        dllPath = join(dirname(abspath(__file__)), dllName)  # type: str
        if not exists(dllPath):
            raise TTLibError(
                '{} not found next to this script.\nDownload TTLib.zip from ramensoftware.com and copy {} here.'.format(
                    dllName, dllName))
        self.__m_lib = WinDLL(dllPath)  # TTLib is __stdcall -> WinDLL
        self._declare()
        self.__m_loaded = False  # type: bool

    def _declare(self):
        """
        :return:
        """
        L = self.__m_lib
        HANDLE, HWND, BOOL, DWORD = c_void_p, c_void_p, c_int, c_uint32
        INTP = POINTER(c_int)
        L.TTLib_Init.restype = DWORD
        L.TTLib_Uninit.restype = BOOL
        L.TTLib_LoadIntoExplorer.restype = DWORD
        L.TTLib_IsLoadedIntoExplorer.restype = BOOL
        L.TTLib_UnloadFromExplorer.restype = BOOL
        L.TTLib_ManipulationStart.restype = BOOL
        L.TTLib_ManipulationEnd.restype = BOOL
        L.TTLib_GetMainTaskbar.restype = HANDLE
        L.TTLib_GetButtonGroupCount.argtypes = [HANDLE, INTP]
        L.TTLib_GetButtonGroupCount.restype = BOOL
        L.TTLib_GetButtonGroup.argtypes = [HANDLE, c_int]
        L.TTLib_GetButtonGroup.restype = HANDLE
        L.TTLib_ButtonGroupMove.argtypes = [HANDLE, c_int, c_int]
        L.TTLib_ButtonGroupMove.restype = BOOL
        L.TTLib_GetButtonGroupType.argtypes = [HANDLE, INTP]
        L.TTLib_GetButtonGroupType.restype = BOOL
        L.TTLib_GetButtonGroupAppId.argtypes = [HANDLE, c_wchar_p, c_size_t]
        L.TTLib_GetButtonGroupAppId.restype = c_size_t
        L.TTLib_GetButtonCount.argtypes = [HANDLE, INTP]
        L.TTLib_GetButtonCount.restype = BOOL
        L.TTLib_GetButton.argtypes = [HANDLE, c_int]
        L.TTLib_GetButton.restype = HANDLE
        L.TTLib_GetButtonWindow.argtypes = [HANDLE]
        L.TTLib_GetButtonWindow.restype = HWND

    def ensureLoaded(self):
        """
        :return: None
        """
        if self.__m_loaded:
            return
        err = self.__m_lib.TTLib_Init()  # type: int
        if err != 0:
            raise TTLibError('TTLib_Init failed (code {}).'.format(err))
        err = self.__m_lib.TTLib_LoadIntoExplorer()  # type: int
        if err != 0:
            self.__m_lib.TTLib_Uninit()
            raise TTLibError(
                'TTLib_LoadIntoExplorer failed (code {}).\n'
                'Usually means your Windows version is newer than TTLib 5.9 '
                'supports (Win10 build > 19041 / Windows 11), or it needs to '
                'run elevated.'.format(err))
        self.__m_loaded = True  # type: bool

    def close(self):
        """
        :return:
        """
        if self.__m_loaded:
            try:
                self.__m_lib.TTLib_UnloadFromExplorer()
            finally:
                self.__m_lib.TTLib_Uninit()
                self.__m_loaded = False  # type: bool

    def _groupCount(self, htaskbar):
        n = c_int(0)  # type: c_int
        if not self.__m_lib.TTLib_GetButtonGroupCount(htaskbar, byref(n)):
            raise TTLibError('Could not read taskbar button-group count.')
        return n.value

    def _groupAppid(self, hgroup):
        buf = create_unicode_buffer(MAX_APPID_LENGTH)
        self.__m_lib.TTLib_GetButtonGroupAppId(hgroup, buf, MAX_APPID_LENGTH)
        return buf.value

    def _groupType(self, hgroup):
        t = c_int(0)  # type: c_int
        self.__m_lib.TTLib_GetButtonGroupType(hgroup, byref(t))
        return self.GROUPTYPE.get(t.value, 'unknown')

    def _groupContainsHwnd(self, hgroup, hwnd):
        n = c_int(0)  # type: c_int
        if not self.__m_lib.TTLib_GetButtonCount(hgroup, byref(n)):
            return False
        for b in range(n.value):
            hBtn = self.__m_lib.TTLib_GetButton(hgroup, b)
            if hBtn:
                win = self.__m_lib.TTLib_GetButtonWindow(hBtn)
                if win and int(win) == int(hwnd):
                    return True
        return False

    def _findGroupIndex(self, htaskbar, hwnd):
        for g in range(self._groupCount(htaskbar)):
            hgroup = self.__m_lib.TTLib_GetButtonGroup(htaskbar, g)
            if hgroup and self._groupContainsHwnd(hgroup, hwnd):
                return g
        return -1

    def step(self, hwnd, direction):
        """
        Move the group owning hwnd by ONE slot. Returns (old, new); equal = at edge.
        :param hwnd: int
        :param direction: int
        :return:
        """
        self.ensureLoaded()
        self.__m_lib.TTLib_ManipulationStart()
        try:
            hTaskbar = self.__m_lib.TTLib_GetMainTaskbar()
            if not hTaskbar:
                raise TTLibError('Could not get the main taskbar handle.')
            count = self._groupCount(hTaskbar)  # type: int
            g = self._findGroupIndex(hTaskbar, hwnd)  # type: int
            if g < 0:
                raise TTLibError(
                    "This window's taskbar button wasn't found.\n"
                    'Make sure the window is visible and shows on the taskbar.')
            target = max(0, min(count - 1, g + (1 if direction > 0 else -1)))  # type: int
            if target != g and not self.__m_lib.TTLib_ButtonGroupMove(hTaskbar, g, target):
                raise TTLibError('TTLib_ButtonGroupMove failed.')
            return g, target
        finally:
            self.__m_lib.TTLib_ManipulationEnd()

    def listOrder(self):
        """
        :return: list[str | unicode]
        """
        self.ensureLoaded()
        self.__m_lib.TTLib_ManipulationStart()
        try:
            hTaskbar = self.__m_lib.TTLib_GetMainTaskbar()
            out = []
            for g in range(self._groupCount(hTaskbar)):
                hgroup = self.__m_lib.TTLib_GetButtonGroup(hTaskbar, g)
                out.append((self._groupAppid(hgroup) or '(no AppId)', self._groupType(hgroup)))
            return out
        finally:
            self.__m_lib.TTLib_ManipulationEnd()
