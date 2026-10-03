import os
import sys

import tkinter as tk
from tkinter import filedialog

from dshow import Player
from dshow.winapi import *

INITIAL_VOLUME = 50
POSITION_UPDATE_TIME_MS = 200


class Timer():
    """A simple tkinter timer
    """

    def __init__(self, root, ms, callback):
        self._root = root
        self._ms = ms
        self._callback = callback

    def start(self):
        self._running = True
        self._root.after(self._ms, self._run)

    def stop(self):
        self._running = False

    def _run(self):
        if self._running:
            self._callback()
            self._root.after(self._ms, self._run)


class Main:
    """A simple media player using DirectShow and tkinter
    """

    def __init__(self, root):
        self.root = root
        self.is_fullscreen = False
        self.is_paused = False
        self.media_duration = 0

        # tkinter's slider widget (Scale) calls callback also when its value was changed programmatically.
        # We use this to distinguish between user and programmatic (timer) value changes.
        self.is_timer = False

        root.withdraw()
        root.title("Media Player")

        self.create_ui()

        # Create a directshow media player
        self.mediaplayer = Player(
            self.video_frame.winfo_id(),
            volume = INITIAL_VOLUME / 100,
        )

        def on_click(event):
            if self.mediaplayer.has_media():
                self.play_pause()

        self.video_frame.bind("<Button-1>", on_click)

        def on_mouse_dbl_click(event):
            if not self.mediaplayer.has_video():
                return
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                self.geom = root.winfo_geometry()
                rc = RECT()
                user32.GetWindowRect(user32.GetDesktopWindow(), byref(rc))
                user32.SetParent(self.video_frame.winfo_id(), None)
                user32.SetWindowPos(self.video_frame.winfo_id(), HWND_TOPMOST, 0, 0, rc.right, rc.bottom, 0)
            else:
                rc = RECT()
                user32.GetClientRect(root.winfo_id(), byref(rc))
                user32.SetParent(self.video_frame.winfo_id(), root.winfo_id())
                root.geometry('0x0')
                root.update()
                root.geometry(self.geom)

            self.play_pause()

        self.video_frame.bind("<Double-Button-1>", on_mouse_dbl_click)

        # Since DirectShow is Windows only, we can use native Windows API
        # functions to support DND from Explorer.
        def on_WM_DROPFILES(hwnd, wparam, lparam):
            file_buffer = create_unicode_buffer(MAX_PATH)
            shell32.DragQueryFileW(wparam, 0, file_buffer, MAX_PATH)
            shell32.DragFinish(wparam)
            root.after(1, lambda f=file_buffer[:].split('\0', 1)[0]: self.load_file(f))

        self.mediaplayer.register_message_callback(WM_DROPFILES, on_WM_DROPFILES)
        shell32.DragAcceptFiles(self.video_frame.winfo_id(), 1)

        root.geometry("640x480")
        root.minsize(300, 68)
        root.update()
        root.deiconify()

        self.timer = Timer(root, POSITION_UPDATE_TIME_MS, self.update_ui)

        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])

    def create_ui(self):
        """Set up the user interface
        """
        menubar = tk.Menu(root)
        menu = tk.Menu(menubar, tearoff = False)
        menu.add_command(label = "Open File", accelerator = "Ctrl+O", command = self.open_file, underline = 0)
        root.bind_all("<Control-o>", self.open_file)
        menu.add_command(label = "Close File", accelerator = "Ctrl+W", command = self.close_file, underline = 0)
        root.bind_all("<Control-w>", self.close_file)
        menu.add_separator()
        menu.add_command(label = "Exit", accelerator = "Ctrl+Q", command = root.quit, underline = 1)
        menubar.add_cascade(label = "File", menu = menu, underline = 0)
        root.config(menu=menubar)

        self.video_frame = tk.Frame(root)
        self.video_frame.pack(expand = True, fill = tk.BOTH)
        self.video_frame.configure(bg="black")

        def on_resize(event):
            self.slider_position.config(length=event.width - 20)

        self.video_frame.bind("<Configure>", on_resize)

        self.slider_position = tk.Scale(root, from_=0, to=2000, orient=tk.HORIZONTAL, showvalue=False, state ="disabled", command=self.set_position)
        self.slider_position.pack(pady=3)

        def on_click(event):
            self.is_timer = False
            self.slider_position.set(int(2000 * event.x / self.slider_position.winfo_width()))

        self.slider_position.bind("<Button-1>", on_click)

        self.button_play = tk.Button(root, text="Play", width=7, command=self.play_pause)
        self.button_play.pack(side="left", padx=7, pady=5)

        button_stop = tk.Button(root, text="Stop", width=7, command=self.stop)
        button_stop.pack(side="left")

        self.slider_volume = tk.Scale(root, from_=0, to=100, orient=tk.HORIZONTAL, showvalue=False, command=self.set_volume)  #width=5
        self.slider_volume.set(INITIAL_VOLUME)
        self.slider_volume.pack(side="right", padx=7)

        def on_click(event):
            self.slider_volume.set(int(100 * event.x / self.slider_volume.winfo_width()))

        self.slider_volume.bind("<Button-1>", on_click)

    def play_pause(self):
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.button_play.config(text="Play")
            self.timer.stop()
            self.is_paused = True
        else:
            if not self.mediaplayer.has_media():
                return self.open_file()
            self.mediaplayer.play()
            self.button_play.config(text="Pause")
            self.timer.start()
            self.is_paused = False

    def stop(self):
        """Stop player
        """
        self.timer.stop()
        self.mediaplayer.stop()
        self.button_play.config(text="Play")
        self.is_timer = True
        self.slider_position.set(0)

    def open_file(self, *args):
        res = filedialog.askopenfile(filetypes = [("All Files (*.*)", "*.*")])
        if res:
            self.load_file(res.name)

    def load_file(self, filename):
        if self.mediaplayer.has_media():
            self.close_file()
        ok = self.mediaplayer.load_media_file(filename)
        if ok:
            self.media_duration = self.mediaplayer.get_duration()
            self.play_pause()
            self.root.title(os.path.basename(filename))
            # media_duration would be 0 e.g. for HLS livestreams, where seeking is impossible
            if self.media_duration > 0:
                self.slider_position.config(state="normal")

    def close_file(self, *args):
        """Close/unload current media file
        """
        self.stop()
        self.mediaplayer.close_file()
        self.slider_position.config(state="disabled")
        self.root.title("Media Player")

    def set_volume(self, volume):
        """Set the volume
        """
        self.mediaplayer.set_volume(int(volume) / 100)

    def set_position(self, pos):
        """Set the media time according to the time slider.
        """
        if self.is_timer:
            self.is_timer = False
        else:
            self.mediaplayer.set_time(self.media_duration * int(pos) / 2000.0)

    def update_ui(self):
        """Update the time slider according to the current media time.
        """
        val = int(self.mediaplayer.get_time() / self.media_duration * 2000)
        self.is_timer = True
        self.slider_position.set(val)
        # No need for a timer if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.stop()
            if not self.is_paused:
                self.stop()


if __name__ == "__main__":
    root = tk.Tk()
    main = Main(root)
    root.mainloop()
