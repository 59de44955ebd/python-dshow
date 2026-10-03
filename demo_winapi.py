import os
import sys

from dshow import Player
from dshow.winapi import *

INITIAL_VOLUME = 50
POSITION_UPDATE_TIME_MS = 200


class Main():
    """A simple Media Player using DirectShow and Windows API
    """

    def __init__(self):
        self.is_fullscreen = False
        self.is_paused = False
        self.media_duration = 0

        self.h_menu = user32.CreateMenu()
        hmenu_child = user32.CreateMenu()
        user32.AppendMenuW(self.h_menu, MF_POPUP, hmenu_child, "&File")
        user32.AppendMenuW(hmenu_child, MF_STRING, 1, "&Open File")
        user32.AppendMenuW(hmenu_child, MF_STRING, 2, "&Close File")
        user32.AppendMenuW(hmenu_child, MF_SEPARATOR, -1, "")
        user32.AppendMenuW(hmenu_child, MF_STRING, 3, "E&xit")

        accels = []
        accels.append((FCONTROL, ord('O'), 1))
        accels.append((FCONTROL, ord('W'), 2))

        acc_table = (ACCEL * len(accels))()
        for (i, acc) in enumerate(accels):
            acc_table[i] = ACCEL(1 | acc[0], acc[1], acc[2])
        self.haccel = user32.CreateAcceleratorTableW(acc_table, len(accels))

        def _window_proc_callback(hwnd, msg, wparam, lparam):
            if msg == WM_CLOSE:
                self.quit()

            elif msg == WM_TIMER:
                self.update_ui()

            elif msg == WM_SIZE:
                width, height = lparam & 0xFFFF, (lparam >> 16) & 0xFFFF
                user32.SetWindowPos(self.hwnd_video_frame, 0, 0, 0, width, height - 70, SWP_NOMOVE)
                user32.SetWindowPos(self.hwnd_button_play, 0, 10, height - 33, 0, 0, SWP_NOSIZE)
                user32.SetWindowPos(self.hwnd_button_stop, 0, 95, height - 33, 0, 0, SWP_NOSIZE)
                user32.SetWindowPos(self.hwnd_slider_position, 0, 7, height - 60, width - 14, 23, 0)
                user32.SetWindowPos(self.hwnd_slider_volume, 0, width - 107, height - 33, 0, 0, SWP_NOSIZE)

            elif msg == WM_GETMINMAXINFO:
                mmi = cast(lparam, POINTER(MINMAXINFO)).contents
                mmi.ptMinTrackSize = POINT(320, 129)
                return 0

            elif msg == WM_HSCROLL:
                if lparam == self.hwnd_slider_position:
                    lo, hi, = wparam & 0xFFFF, (wparam >> 16) & 0xFFFF
                    if lo == TB_ENDTRACK:
                        return 0
                    if lo in (TB_PAGEDOWN, TB_PAGEUP):  # Click into slider
                        pt = POINT()
                        user32.GetCursorPos(byref(pt))
                        user32.MapWindowPoints(None, self.hwnd_slider_position, byref(pt), 1)
                        rc = RECT()
                        user32.GetWindowRect(self.hwnd_slider_position, byref(rc))
                        hi = int((pt.x - 10) / (rc.right - rc.left - 20) * 2000)
                        user32.SendMessageW(self.hwnd_slider_position, TBM_SETPOS, 1, hi)
                    self.set_position(hi)

                elif lparam == self.hwnd_slider_volume:
                    lo, hi, = wparam & 0xFFFF, (wparam >> 16) & 0xFFFF
                    if lo == TB_ENDTRACK:
                        return 0
                    if lo in (TB_PAGEDOWN, TB_PAGEUP):  # Click into slider
                        pt = POINT()
                        user32.GetCursorPos(byref(pt))
                        user32.MapWindowPoints(None, self.hwnd_slider_volume, byref(pt), 1)
                        rc = RECT()
                        user32.GetWindowRect(self.hwnd_slider_volume, byref(rc))
                        hi = int((pt.x - 10) / (rc.right - rc.left - 20) * 100)
                        user32.SendMessageW(self.hwnd_slider_volume, TBM_SETPOS, 1, hi)
                    self.set_volume(hi)

            elif msg == WM_COMMAND:
                command_id = LOWORD(wparam)
                if lparam == 0:
                    if command_id == 1:
                        self.open_file()
                    elif command_id == 2:
                        self.close_file()
                    elif command_id == 3:
                        self.quit()
                elif lparam == self.hwnd_button_play:
                    if command_id == BN_CLICKED:
                        self.play_pause()
                elif lparam == self.hwnd_button_stop:
                    if command_id == BN_CLICKED:
                        self.stop()

            elif msg == WM_DROPFILES:
                cnt = shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                file_buffer = create_unicode_buffer(MAX_PATH)
                shell32.DragQueryFileW(wparam, 0, file_buffer, MAX_PATH)
                shell32.DragFinish(wparam)
                self.load_file(file_buffer[:].split('\0', 1)[0])

            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self.windowproc = WNDPROC(_window_proc_callback)

        newclass = WNDCLASSEXW()
        newclass.lpfnWndProc = self.windowproc
        newclass.lpszClassName = "MediaPlayer"
        newclass.hbrBackground = COLOR_3DFACE + 1
        newclass.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        newclass.style = CS_VREDRAW | CS_HREDRAW
        user32.RegisterClassExW(byref(newclass))

        hwnd_desktop = user32.GetDesktopWindow()
        rc = RECT()
        user32.GetClientRect(hwnd_desktop, byref(rc))
        cx, cy = 654, 517
        x, y = (rc.right - cx) // 2, (rc.bottom - cy) // 2

        self.hwnd = user32.CreateWindowExW(
            WS_EX_ACCEPTFILES,
            newclass.lpszClassName,
            "Media Player",
            WS_OVERLAPPEDWINDOW,
            x, y, cx, cy,
            0,
            self.h_menu,
            None, 0
        )

        self.create_ui()

        # Create a directshow media player
        self.mediaplayer = Player(
            self.hwnd_video_frame,
            volume = INITIAL_VOLUME / 100,
        )

        def on_WM_LBUTTONDOWN(hwnd, wparam, lparam):
            if self.mediaplayer.has_media():
                self.play_pause()

        self.mediaplayer.register_message_callback(WM_LBUTTONDOWN, on_WM_LBUTTONDOWN)

        def on_WM_LBUTTONDBLCLK(hwnd, wparam, lparam):
            if not self.mediaplayer.has_video():
                return
            self.is_fullscreen = not self.is_fullscreen
            if self.is_fullscreen:
                rc = RECT()
                user32.GetWindowRect(user32.GetDesktopWindow(), byref(rc))
                user32.SetParent(self.hwnd_video_frame, None)
                user32.SetWindowPos(self.hwnd_video_frame, HWND_TOPMOST, 0, 0, rc.right, rc.bottom, 0)
            else:
                rc = RECT()
                user32.GetClientRect(self.hwnd, byref(rc))
                user32.SetParent(self.hwnd_video_frame, self.hwnd)
                user32.SetWindowPos(self.hwnd_video_frame, 0, 0, 0, rc.right, rc.bottom - 70, SWP_NOMOVE)
            self.play_pause()

        self.mediaplayer.register_message_callback(WM_LBUTTONDBLCLK, on_WM_LBUTTONDBLCLK)

        user32.ShowWindow(self.hwnd, SW_SHOWNORMAL)

        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])

    def run(self):
        msg = MSG()
        while user32.GetMessageW(byref(msg), None, 0, 0):
            if user32.TranslateAcceleratorW(self.hwnd, self.haccel, byref(msg)) or user32.IsDialogMessage(self.hwnd, byref(msg)):
                continue
            user32.TranslateMessage(byref(msg))
            user32.DispatchMessageW(byref(msg))
        return 0

    def quit(self):
        user32.PostQuitMessage(0)

    def timer_start(self):
        user32.SetTimer(self.hwnd, 1, POSITION_UPDATE_TIME_MS, 0)  # 1 is our timer id

    def timer_stop(self):
        user32.KillTimer(self.hwnd, 1)

    def create_ui(self):
        """Set up the user interface
        """
        self.dummy_proc = WNDPROC(user32.DefWindowProcW)
        newclass = WNDCLASSEXW()
        newclass.lpfnWndProc = self.dummy_proc
        newclass.lpszClassName = "VideoFrame"
        newclass.hbrBackground = gdi32.GetStockObject(BLACK_BRUSH)
        newclass.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        newclass.style = CS_VREDRAW | CS_HREDRAW | CS_DBLCLKS
        user32.RegisterClassExW(byref(newclass))

        self.hwnd_video_frame = user32.CreateWindowExW(
            0,
            newclass.lpszClassName,
            "VideoFrame",
            WS_CHILD | WS_VISIBLE,
            0, 0, 0, 0,
            self.hwnd,
            None, None, 0
        )

        h_font_shell = gdi32.CreateFontW(
            -11, 0, 0, 0, FW_DONTCARE, 0, 0, 0, ANSI_CHARSET, OUT_TT_PRECIS,
            CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH | FF_DONTCARE, "Segoe UI"
        )

        self.hwnd_button_play = user32.CreateWindowExW(
            0,
            WC_BUTTON,
            "Play",
            WS_CHILD | WS_VISIBLE,
            0, 0, 80, 23,
            self.hwnd,
            None, None, 0
        )
        user32.SendMessageW(self.hwnd_button_play, WM_SETFONT, h_font_shell, 1)

        self.hwnd_button_stop = user32.CreateWindowExW(
            0,
            WC_BUTTON,
            "Stop",
            WS_CHILD | WS_VISIBLE,
            0, 0, 80, 23,
            self.hwnd,
            None, None, 0
        )
        user32.SendMessageW(self.hwnd_button_stop, WM_SETFONT, h_font_shell, 1)

        self.hwnd_slider_position = user32.CreateWindowExW(
            0,
            WC_TRACKBAR,
            "",
            WS_CHILD | WS_VISIBLE | WS_DISABLED,
            0, 0, 0, 0,
            self.hwnd,
            None, None, 0
        )
        user32.SendMessageW(self.hwnd_slider_position, TBM_SETRANGEMAX, 0, 2000)
        user32.SendMessageW(self.hwnd_slider_position, TBM_SETPAGESIZE, 0, 1)

        self.hwnd_slider_volume = user32.CreateWindowExW(
            0,
            WC_TRACKBAR,
            "",
            WS_CHILD | WS_VISIBLE,
            0, 0, 100, 23,
            self.hwnd,
            None, None, 0
        )
        user32.SendMessageW(self.hwnd_slider_volume, TBM_SETRANGEMAX, 0, 100)
        user32.SendMessageW(self.hwnd_slider_volume, TBM_SETPAGESIZE, 0, 1)
        user32.SendMessageW(self.hwnd_slider_volume, TBM_SETPOS, 1, INITIAL_VOLUME)

    def play_pause(self):
        """Toggle play/pause status
        """
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            user32.SetWindowTextW(self.hwnd_button_play, "Play")
            self.timer_stop()
            self.is_paused = True
        else:
            if not self.mediaplayer.has_media():
                return self.open_file()
            self.mediaplayer.play()
            user32.SetWindowTextW(self.hwnd_button_play, "Pause")
            self.is_paused = False
            self.timer_start()
        user32.EnableWindow(self.hwnd_slider_position, 1)

    def stop(self):
        """Stop player
        """
        self.mediaplayer.stop()
        self.timer_stop()
        user32.SetWindowTextW(self.hwnd_button_play, "Play")
        user32.SendMessageW(self.hwnd_slider_position, TBM_SETPOS, 1, 0)

    def open_file(self):
        """Open a media file in player
        """
        file_buffer = create_unicode_buffer(MAX_PATH)
        ofn = OPENFILENAMEW()
        ofn.hwndOwner = self.hwnd
        ofn.lpstrTitle = "Choose Media File"
        ofn.lpstrFile = cast(file_buffer, LPWSTR)
        ofn.nMaxFile = MAX_PATH
        ofn.Flags = OFN_ENABLESIZING | OFN_PATHMUSTEXIST
        if not comdlg32.GetOpenFileNameW(byref(ofn)):
            return
        self.load_file(file_buffer[:].split("\0", 1)[0])

    def load_file(self, filename):
        if self.mediaplayer.has_media():
            self.close_file()
        ok = self.mediaplayer.load_media_file(filename)
        if ok:
            self.media_duration = self.mediaplayer.get_duration()
            self.play_pause()
            user32.SetWindowTextW(self.hwnd, os.path.basename(filename))
            # media_duration would be 0 e.g. for HLS livestreams, where seeking is impossible
            user32.EnableWindow(self.hwnd_slider_position, int(self.media_duration > 0))

    def close_file(self):
        """Close/unload current media file
        """
        self.stop()
        self.mediaplayer.close_file()
        user32.EnableWindow(self.hwnd_slider_position, 0)
        user32.SetWindowTextW(self.hwnd, "Media Player")

    def set_volume(self, volume):
        """Set the volume
        """
        self.mediaplayer.set_volume(volume / 100)

    def set_position(self, pos):
        """Set the media time according to the time slider
        """
        self.mediaplayer.set_time(self.media_duration * pos / 2000.0)

    def update_ui(self):
        """Update the time slider according to the current media time.
        """
        if self.media_duration:
            val = int(self.mediaplayer.get_time() / self.media_duration * 2000)
            user32.SendMessageW(self.hwnd_slider_position, TBM_SETPOS, 1, val)
        # No need for a timer if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer_stop()
            if not self.is_paused:
                self.stop()


if __name__ == "__main__":
    main = Main()
    sys.exit(main.run())
