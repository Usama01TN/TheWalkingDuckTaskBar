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
from ManyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, \
    QSpinBox, QCheckBox, QFileDialog, QMainWindow
from ManyQt.QtCore import Qt, QTimer, pyqtSlot
from ManyQt.QtGui import QIcon
from os.path import abspath, dirname, join, basename
from sys import path

if dirname(__file__) not in path:
    path.append(dirname(__file__))

try:
    from .walkingduck import makeDuckIcon, QuackPlayer, TaskbarMover, TTLibError
except:
    from walkingduck import makeDuckIcon, QuackPlayer, TaskbarMover, TTLibError


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    """
    MainWindow class.
    """
    WALK_INTERVAL_MS = 110  # type: int

    def __init__(self, *args, **kwargs):
        """
        :param soundArg: str | unicode | QString | None
        :param args: any
        :param kwargs: any
        """
        soundArg = kwargs.pop('soundArg', None)  # type: str | None
        subArgs = (x for x in args if not (isinstance(x, str) or hasattr(x, 'encode')))
        super(MainWindow, self).__init__(*subArgs, **kwargs)
        for arg in args:
            if isinstance(arg, str) or hasattr(arg, 'encode'):
                soundArg = arg  # type: str
                break
        self.setWindowTitle(self.tr('Quacking Duck Taskbar Mover'))
        self.resize(600, 280)
        self.__m_framesRight = [makeDuckIcon(p) for p in range(4)]  # type: list[QIcon]
        self.__m_framesLeft = [makeDuckIcon(p, facingRight=False) for p in range(4)]  # type: list[QIcon]
        self.__m_idleRight = makeDuckIcon(0, idle=True)  # type: QIcon
        self.__m_idleLeft = makeDuckIcon(0, facingRight=False, idle=True)  # type: QIcon
        self.__m_facingRight = True  # type: bool
        self.__m_frame = 0  # type: int
        self.setWindowIcon(self.__m_idleRight)
        # Audio: load from CLI arg, or quack.wav next to the script, if present.
        self.__m_quack = QuackPlayer()  # type: QuackPlayer
        self.__m_quack.load(soundArg or join(dirname(abspath(__file__)), 'quack.mp3'))
        self.__m_mover = None  # type: TaskbarMover | None
        self.__m_initError = None  # type: str | None
        try:
            self.__m_mover = TaskbarMover()  # type: TaskbarMover
        except TTLibError as e:
            self.__m_initError = str(e)  # type: str
        self.__m_dir = 0  # type: int
        self.__m_stepTimer = QTimer(self)  # type: QTimer
        self.__m_stepTimer.timeout.connect(self._stepTick)
        self.__m_walkTimer = QTimer(self)  # type: QTimer
        self.__m_walkTimer.setInterval(self.WALK_INTERVAL_MS)
        self.__m_walkTimer.timeout.connect(self._walkTick)
        title = QLabel(self.tr("Walk this window's duck across the real taskbar"))  # type: QLabel
        title.setStyleSheet('font-size:15px; font-weight:bold; padding:10px;')
        title.setAlignment(Qt.AlignCenter)
        self.__m_status = QLabel(
            self.tr(self.__m_initError or 'Ready. Load a duck sound, then press Walk.'))  # type: QLabel
        self.__m_status.setWordWrap(True)
        self.__m_status.setAlignment(Qt.AlignCenter)
        self.__m_status.setStyleSheet('color:#444; padding:8px;')
        self.__m_leftBtn = QPushButton(self.tr(u'\U0001F986  Walk to start'))  # type: QPushButton
        self.__m_rightBtn = QPushButton(self.tr(u'Walk to end  \U0001F986'))  # type: QPushButton
        self.__m_stopBtn = QPushButton(self.tr(u'\u25A0  Stop'))  # type: QPushButton
        self.__m_orderBtn = QPushButton(self.tr('Show current taskbar order'))  # type: QPushButton
        for b in (self.__m_leftBtn, self.__m_rightBtn, self.__m_stopBtn, self.__m_orderBtn):
            b.setMinimumHeight(34)
        self.__m_leftBtn.clicked.connect(lambda: self.startWalk(-1))
        self.__m_rightBtn.clicked.connect(lambda: self.startWalk(+1))
        self.__m_stopBtn.clicked.connect(lambda: self.stopWalk(self.tr('Stopped.')))
        self.__m_orderBtn.clicked.connect(self.showOrder)
        self.__m_speed = QSpinBox()  # type: QSpinBox
        self.__m_speed.setRange(60, 1000)
        self.__m_speed.setSingleStep(20)
        self.__m_speed.setValue(620)
        self.__m_speed.setSuffix(self.tr(' ms / slot'))
        self.__m_soundChk = QCheckBox(self.tr('Quack on every step'))  # type: QCheckBox
        self.__m_soundChk.setChecked(True)
        if not self.__m_quack.available():
            self.__m_soundChk.setChecked(False)
            self.__m_soundChk.setEnabled(False)
            self.__m_soundChk.setText(self.tr('Quack (QtMultimedia unavailable)'))
        self.__m_chooseBtn = QPushButton(self.tr('Choose duck sound...'))  # type: QPushButton
        self.__m_chooseBtn.clicked.connect(self.chooseSound)
        self.__m_chooseBtn.setEnabled(self.__m_quack.available())
        self.__m_soundLabel = QLabel()  # type: QLabel
        self.__m_soundLabel.setAlignment(Qt.AlignCenter)
        self.__m_soundLabel.setStyleSheet('color:#666;')
        self._updateSoundLabel()
        optsRow = QHBoxLayout()  # type: QHBoxLayout
        optsRow.addStretch(1)
        optsRow.addWidget(QLabel(self.tr('Step speed:')))
        optsRow.addWidget(self.__m_speed)
        optsRow.addSpacing(14)
        optsRow.addWidget(self.__m_soundChk)
        optsRow.addSpacing(14)
        optsRow.addWidget(self.__m_chooseBtn)
        optsRow.addStretch(1)
        walkRow = QHBoxLayout()  # type: QHBoxLayout
        walkRow.addWidget(self.__m_leftBtn)
        walkRow.addWidget(self.__m_rightBtn)
        walkRow.addWidget(self.__m_stopBtn)
        base = QWidget()  # type: QWidget
        layout = QVBoxLayout(base)  # type: QVBoxLayout
        layout.addWidget(title)
        layout.addLayout(walkRow)
        layout.addLayout(optsRow)
        layout.addWidget(self.__m_soundLabel)
        layout.addWidget(self.__m_orderBtn)
        layout.addWidget(self.__m_status)
        self._setRunning(False)
        if not self.__m_mover:
            for b in (self.__m_leftBtn, self.__m_rightBtn, self.__m_stopBtn, self.__m_orderBtn):
                b.setEnabled(False)
        self.setCentralWidget(base)

    def _updateSoundLabel(self):
        """
        :return:
        """
        if self.__m_quack.path:
            self.__m_soundLabel.setText(self.tr('Sound: ') + basename(self.__m_quack.path))
        else:
            self.__m_soundLabel.setText(self.tr(u'Sound: (none loaded - click \u201cChoose duck sound\u2026\u201d)'))

    @pyqtSlot()
    def chooseSound(self):
        """
        :return:
        """
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr('Choose a duck sound'), '',
            self.tr('Audio files (*.wav *.mp3 *.ogg *.m4a *.wma *.aac);;All files (*)'))  # type: str, str
        if path:
            if self.__m_quack.load(path):
                self._updateSoundLabel()
                self.__m_quack.play()  # quick preview
            else:
                QMessageBox.warning(self, self.tr('Could not load sound'), self.tr('That file could not be loaded.'))

    def _setRunning(self, running):
        """
        :param running: bool
        :return:
        """
        if self.__m_mover:
            self.__m_leftBtn.setEnabled(not running)
            self.__m_rightBtn.setEnabled(not running)
            self.__m_orderBtn.setEnabled(not running)
            self.__m_speed.setEnabled(not running)
            self.__m_chooseBtn.setEnabled(not running)
            self.__m_stopBtn.setEnabled(running)

    def _quack(self):
        """
        :return:
        """
        if self.__m_soundChk.isChecked() and self.__m_quack.path:
            self.__m_quack.play()

    def _walkTick(self):
        """
        :return:
        """
        self.__m_frame = (self.__m_frame + 1) % 4  # type: int
        frames = self.__m_framesRight if self.__m_facingRight else self.__m_framesLeft  # type: list[QIcon]
        self.setWindowIcon(frames[self.__m_frame])

    def _setIdleIcon(self):
        """
        :return:
        """
        self.__m_frame = 0  # type: int
        self.setWindowIcon(self.__m_idleRight if self.__m_facingRight else self.__m_idleLeft)

    @pyqtSlot(int)
    def startWalk(self, direction):
        """
        :param direction: int
        :return: None
        """
        if not self.__m_mover or self.__m_stepTimer.isActive():
            return
        self.__m_dir = direction  # type: int
        self.__m_facingRight = direction > 0  # type: bool
        self.__m_stepTimer.setInterval(self.__m_speed.value())
        self._setRunning(True)
        self.__m_status.setText(self.tr('Waddling {}...'.format('left' if direction < 0 else 'right')))
        self.__m_walkTimer.start()
        self._stepTick()
        if self.__m_dir != 0 and not self.__m_stepTimer.isActive():
            self.__m_stepTimer.start()

    def _stepTick(self):
        """
        :return: None
        """
        if not self.__m_mover:
            return
        try:
            old, new = self.__m_mover.step(int(self.winId()), self.__m_dir)  # type: int, int
            if old == new:
                self.stopWalk(self.tr('Reached the {} edge (position {}).'.format(
                    'left' if self.__m_dir < 0 else 'right', new)))
                return
            self._quack()
            self.__m_status.setText(self.tr('Now at taskbar position {}.').format(new))
            if not self.__m_stepTimer.isActive():
                self.__m_stepTimer.start()
        except Exception as e:  # noqa: BLE001
            self.stopWalk(self.tr('Move failed.'))
            QMessageBox.warning(self, self.tr('Taskbar move failed'), str(e))

    @pyqtSlot('QString')
    @pyqtSlot(str)
    def stopWalk(self, msg=''):
        """
        :param msg: str | unicode | QString
        :return: None
        """
        self.__m_stepTimer.stop()
        self.__m_walkTimer.stop()
        self.__m_dir = 0  # type: int
        self._setIdleIcon()
        self._setRunning(False)
        if msg:
            self.__m_status.setText(msg)

    @pyqtSlot()
    def showOrder(self):
        """
        :return: None
        """
        if not self.__m_mover:
            return
        try:
            lines = ['{:>2}. {}  [{}]'.format(
                i, appid, kind) for i, (appid, kind) in enumerate(self.__m_mover.listOrder())]  # type: list[str]
            QMessageBox.information(
                self, self.tr('Taskbar order (left to right)'), self.tr('\n'.join(lines) or '(no groups found)'))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, self.tr('Could not read taskbar'), str(e))

    def closeEvent(self, event):
        """
        :param event: QCloseEvent
        :return:
        """
        self.__m_stepTimer.stop()
        self.__m_walkTimer.stop()
        self.__m_quack.stop()
        if self.__m_mover:
            self.__m_mover.close()
        super(MainWindow, self).closeEvent(event)
