import os
import sys

from . import Player
from .winapi import *


class Main():

    def __init__(
        self,
        media_file,
        resize_to_video = True,
        x = CW_USEDEFAULT, y = CW_USEDEFAULT, cx = CW_USEDEFAULT, cy =CW_USEDEFAULT
    ):
        self.is_fullscreen = False

        def _window_proc_callback(hwnd, msg, wparam, lparam):
            if msg == WM_CLOSE:
                user32.PostQuitMessage(0)
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self.windowproc = WNDPROC(_window_proc_callback)

        newclass = WNDCLASSEXW()
        newclass.lpfnWndProc = self.windowproc
        newclass.lpszClassName = "MediaPlayer"
        newclass.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
        newclass.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        newclass.style = CS_VREDRAW | CS_HREDRAW | CS_DBLCLKS
        user32.RegisterClassExW(byref(newclass))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_ACCEPTFILES,
            newclass.lpszClassName,
            "Media Player",
            WS_OVERLAPPEDWINDOW,
            x, y, cx, cy,
            0, None, None, 0
        )

        windll.dwmapi.DwmSetWindowAttribute(self.hwnd, 20, byref(c_int(1)), sizeof(c_int))

        self.mediaplayer = Player(self.hwnd)

        def on_WM_LBUTTONDOWN(hwnd, wparam, lparam):
            if self.mediaplayer.has_media():
                self.play_pause()

        self.mediaplayer.register_message_callback(WM_LBUTTONDOWN, on_WM_LBUTTONDOWN)

        def on_WM_LBUTTONDBLCLK(hwnd, wparam, lparam):
            if not self.mediaplayer.has_video():
                return
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                user32.SetWindowLongA(self.hwnd, GWL_STYLE, WS_OVERLAPPED)
                user32.ShowWindow(self.hwnd, SW_SHOWMAXIMIZED)
            else:
                user32.ShowWindow(self.hwnd, SW_SHOWNORMAL)
                user32.SetWindowLongA(self.hwnd, GWL_STYLE, WS_OVERLAPPEDWINDOW | WS_VISIBLE)
                user32.SetWindowPos(self.hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_FRAMECHANGED)
            self.play_pause()

        self.mediaplayer.register_message_callback(WM_LBUTTONDBLCLK, on_WM_LBUTTONDBLCLK)

        ok = self.mediaplayer.load_media_file(media_file)
        if ok:
            if resize_to_video and self.mediaplayer.has_video():
                w, h = self.mediaplayer.get_size()
                rc_win, rc_client = RECT(), RECT()
                user32.GetWindowRect(self.hwnd, byref(rc_win))
                user32.GetClientRect(self.hwnd, byref(rc_client))
                ui_width = rc_win.right - rc_win.left - rc_client.right
                ui_height = rc_win.bottom - rc_win.top - rc_client.bottom
                user32.SetWindowPos(self.hwnd, 0, 0, 0, w + ui_width, h + ui_height, SWP_NOMOVE)

            self.play_pause()
            user32.SetWindowTextW(self.hwnd, os.path.basename(media_file))
            user32.ShowWindow(self.hwnd, SW_SHOWNORMAL)
        else:
            print(f"Error: failed to load {media_file}", file=sys.stderr)
            user32.PostQuitMessage(0)

    def run(self):
        msg = MSG()
        while user32.GetMessageW(byref(msg), None, 0, 0):
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))
        return 0

    def play_pause(self):
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
        else:
            self.mediaplayer.play()

    def load_file(self, filename):
        ok = self.mediaplayer.load_media_file(filename)
        if ok:
            self.play_pause()
            user32.SetWindowTextW(self.hwnd, os.path.basename(filename))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        Main(sys.argv[1]).run()
    else:
        print("Usage: python -m dshow MEDIA_FILE", file=sys.stderr)
