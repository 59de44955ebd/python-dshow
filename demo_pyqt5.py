import os
import sys

from PyQt5 import QtWidgets, QtGui, QtCore

from dshow import Player

INITIAL_VOLUME = 50
POSITION_UPDATE_TIME_MS = 200


class MySlider(QtWidgets.QSlider):
    """ A horizontal slider that jumps to clicked position
    """

    def mousePressEvent (self, event):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderHandle, self)
        self.is_pressed_outside = event.button() == QtCore.Qt.LeftButton and not sr.contains(event.pos())
        if self.is_pressed_outside:
            val = int(self.minimum() + ((self.maximum() - self.minimum()) * event.x()) / self.width())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_pressed_outside:
            val = int(self.minimum() + ((self.maximum() - self.minimum()) * event.x()) / self.width())
            self.setValue(val)
            self.sliderMoved.emit(val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        self.sliderMoved.emit(self.value())


class VideoFrame(QtWidgets.QFrame):
    """ A frame that emits mouseEvents as signals
    """
    mouseDown = QtCore.pyqtSignal()
    mmouseDblClick = QtCore.pyqtSignal()

    def mousePressEvent (self, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.mouseDown.emit()
        elif event.type() == QtCore.QEvent.MouseButtonDblClick:
            self.mmouseDblClick.emit()


class Main(QtWidgets.QMainWindow):
    """A simple media player using DirectShow and PyQt5
    """

    def __init__(self, master=None):
        self.is_paused = False
        self.media_duration = 0

        QtWidgets.QMainWindow.__init__(self, master)
        self.setWindowTitle("Media Player")
        self.setAcceptDrops(True)

        self.create_ui()

        # Create a directshow media player
        self.mediaplayer = Player(
            int(self.video_frame.winId()),
            volume = INITIAL_VOLUME / 100,
        )

        def on_mouse_down():
            if self.mediaplayer.has_media():
                self.play_pause()

        self.video_frame.mouseDown.connect(on_mouse_down)

        def on_mouse_dbl_click():
            if self.mediaplayer.has_video():
                if self.video_frame.isFullScreen():
                    self.widget.layout().insertWidget(0, self.video_frame)
                    self.setVisible(True)
                else:
                    self.video_frame.setParent(None)
                    self.video_frame.showFullScreen()
                    self.setVisible(False)
                self.play_pause()

        self.video_frame.mmouseDblClick.connect(on_mouse_dbl_click)

        self.resize(640, 480)
        self.show()

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(POSITION_UPDATE_TIME_MS)
        self.timer.timeout.connect(self.update_ui)

        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])

    def dragEnterEvent (self, e):
        if e.mimeData().hasUrls():
            e.accept()

    def dropEvent (self, e):
        self.load_file(e.mimeData().urls()[0].toLocalFile())

    def create_ui(self):
        """Set up the user interface
        """
        file_menu = self.menuBar().addMenu("File")
        open_action = file_menu.addAction("&Open File")
        open_action.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.open_file)

        close_action = file_menu.addAction("&Close File")
        close_action.setShortcut(QtGui.QKeySequence("Ctrl+W"))
        close_action.triggered.connect(self.close_file)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        self.widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.widget)

        vboxlayout = QtWidgets.QVBoxLayout()
        vboxlayout.setContentsMargins(0, 0, 0, 0)

        self.video_frame = VideoFrame()
        palette = self.video_frame.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(0, 0, 0))
        self.video_frame.setPalette(palette)
        self.video_frame.setAutoFillBackground(True)
        vboxlayout.addWidget(self.video_frame)

        self.slider_position = MySlider(QtCore.Qt.Horizontal, self)
        self.slider_position.setToolTip("Position")
        self.slider_position.setMaximum(2000)
        self.slider_position.sliderMoved.connect(self.set_position)
        self.slider_position.setEnabled(False)

        hboxlayout = QtWidgets.QHBoxLayout()
        hboxlayout.setContentsMargins(10, 0, 10, 0)
        hboxlayout.addWidget(self.slider_position)
        vboxlayout.addLayout(hboxlayout)

        hboxlayout = QtWidgets.QHBoxLayout()
        hboxlayout.setContentsMargins(10, 5, 10, 10)

        self.button_play = QtWidgets.QPushButton("Play")
        hboxlayout.addWidget(self.button_play)
        self.button_play.clicked.connect(self.play_pause)

        self.button_stop = QtWidgets.QPushButton("Stop")
        hboxlayout.addWidget(self.button_stop)
        self.button_stop.clicked.connect(self.stop)

        hboxlayout.addStretch(1)

        self.slider_volume = MySlider(QtCore.Qt.Horizontal, self)
        hboxlayout.addWidget(self.slider_volume)
        self.slider_volume.setMinimumWidth(50)
        self.slider_volume.setMaximum(100)
        self.slider_volume.setValue(INITIAL_VOLUME)
        self.slider_volume.setToolTip("Volume")
        self.slider_volume.sliderMoved.connect(self.set_volume)

        vboxlayout.addLayout(hboxlayout)
        self.widget.setLayout(vboxlayout)

    def play_pause(self):
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.button_play.setText("Play")
            self.timer.stop()
            self.is_paused = True
        else:
            if not self.mediaplayer.has_media():
                return self.open_file()
            self.mediaplayer.play()
            self.button_play.setText("Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        self.timer.stop()
        self.button_play.setText("Play")
        self.slider_position.setValue(0)

    def open_file(self):
        """Open a media file in a MediaPlayer
        """
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Media File")
        if not filename:
            return
        self.load_file(filename)

    def load_file(self, filename):
        if self.mediaplayer.has_media():
            self.close_file()
        ok = self.mediaplayer.load_media_file(filename)
        if ok:
            self.media_duration = self.mediaplayer.get_duration()
            self.play_pause()
            self.setWindowTitle(os.path.basename(filename))
            # media_duration would be 0 e.g. for HLS livestreams, where seeking is impossible
            self.slider_position.setEnabled(self.media_duration > 0)

    def close_file(self):
        """Close/unload current media file
        """
        self.stop()
        self.mediaplayer.close_file()
        self.slider_position.setEnabled(False)
        self.setWindowTitle("Media Player")

    def set_volume(self, volume):
        """Set the volume
        """
        self.mediaplayer.set_volume(volume / 100)

    def set_position(self, pos):
        """Set the media time according to the time slider.
        """
        self.mediaplayer.set_time(self.media_duration * pos / 2000.0)

    def update_ui(self):
        """Update the time slider according to the current media time.
        """
        val = int(self.mediaplayer.get_time() / self.media_duration * 2000)
        self.slider_position.setValue(val)
        # No need for a timer if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.stop()
            if not self.is_paused:
                self.stop()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = Main()
    sys.exit(app.exec())
