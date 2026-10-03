import os
import sys

import clr
import System
clr.AddReference('System.Windows.Forms')
from System.Threading import Thread, ThreadStart, ApartmentState
import System.Windows.Forms as WinForms
from System.Drawing import Color, Size

from dshow import Player
from dshow.winapi import *

INITIAL_VOLUME = 50
POSITION_UPDATE_TIME_MS = 200


class Main(WinForms.Form):

    def __init__(self):
        self.is_fullscreen = False
        self.is_paused = False
        self.media_duration = 0

        super().__init__()

        self.Text = "Media Player"
        self.Size = Size(654, 517)
        self.MinimumSize = Size(320, 129)
        self.StartPosition = WinForms.FormStartPosition.CenterScreen

        self.create_ui()
        self.AllowDrop = True

        def on_drag(sender, args):
            args.Effect = WinForms.DragDropEffects.Copy

        self.DragEnter += on_drag

        def on_drop(sender, args):
            if args.Data.GetDataPresent(WinForms.DataFormats.FileDrop):
                files = args.Data.GetData(WinForms.DataFormats.FileDrop)
                self.load_file(files[0])

        self.DragDrop += on_drop

        # Create a directshow media player
        self.mediaplayer = Player(
            self.video_frame.Handle.ToInt32(),
            volume = INITIAL_VOLUME / 100,
        )

        def on_click(sender, args):
            if self.mediaplayer.has_media():
                self.play_pause()

        self.video_frame.Click += on_click

        def on_dblclick(sender, args):
            if not self.mediaplayer.has_video():
                return
            self.is_fullscreen = not self.is_fullscreen
            hwnd_video_frame = self.video_frame.Handle.ToInt32()
            if self.is_fullscreen:
                rc = RECT()
                user32.GetWindowRect(user32.GetDesktopWindow(), byref(rc))
                user32.SetParent(hwnd_video_frame, None)
                self.video_frame.Dock = getattr(WinForms.DockStyle, 'None')
                user32.SetWindowPos(hwnd_video_frame, HWND_TOPMOST, 0, 0, rc.right, rc.bottom, 0)
            else:
                user32.SetParent(hwnd_video_frame, self.Handle.ToInt32())
                self.video_frame.Dock = WinForms.DockStyle.Fill
            self.play_pause()

        self.video_frame.DoubleClick += on_dblclick

        self.timer = WinForms.Timer()
        self.timer.Interval = POSITION_UPDATE_TIME_MS
        self.timer.Tick += self.update_ui

        if len(sys.argv) > 1:
            self.load_file(sys.argv[1])

    def create_ui(self):
        """Set up the user interface
        """
        self.SuspendLayout()

        self.Menu = WinForms.MainMenu()
        m = WinForms.MenuItem('&File')
        self.Menu.MenuItems.Add(m)

        action_item = WinForms.MenuItem('&Open File')
        action_item.Shortcut = WinForms.Shortcut.CtrlO
        action_item.Click += self.open_file
        m.MenuItems.Add(action_item)

        action_item = WinForms.MenuItem('&Close File')
        action_item.Shortcut = WinForms.Shortcut.CtrlW
        action_item.Click += self.close_file
        m.MenuItems.Add(action_item)

        m.MenuItems.Add(WinForms.MenuItem('-'))

        action_item = WinForms.MenuItem('E&xit')
        action_item.Click += self.quit
        m.MenuItems.Add(action_item)

        self.video_frame = WinForms.UserControl()
        self.video_frame.BackColor = Color.Black
        self.video_frame.Dock = WinForms.DockStyle.Fill
        self.Controls.Add(self.video_frame)

        self.panel = WinForms.TableLayoutPanel()
        self.panel.Padding = WinForms.Padding(7, 0, 7, 0)
        self.panel.Height = 70
        self.panel.Dock = WinForms.DockStyle.Bottom
        self.panel.ColumnCount = 3
        self.panel.RowCount = 2
        self.Controls.Add(self.panel)

        self.trackbar_position = WinForms.TrackBar()
        self.trackbar_position.Maximum = 2000
        self.trackbar_position.Dock = WinForms.DockStyle.Bottom
        self.trackbar_position.AutoSize = False
        self.trackbar_position.Height = 30
        self.trackbar_position.TickStyle = getattr(WinForms.TickStyle, 'None')
        self.trackbar_position.Anchor = WinForms.AnchorStyles.Left | WinForms.AnchorStyles.Top | WinForms.AnchorStyles.Right
        self.trackbar_position.Enabled = False
        self.panel.Controls.Add(self.trackbar_position, 0, 0)
        self.panel.SetColumnSpan(self.trackbar_position, 3)
        self.trackbar_position.Scroll += lambda sender, args: self.set_position(self.trackbar_position.Value)

        def on_click(sender, args):
            w = self.trackbar_position.Width - 28
            x = args.X - 14
            pos = max(0, min(2000, int(x / w * 2000)))
            self.trackbar_position.Value = pos
            self.set_position(pos)

        self.trackbar_position.MouseDown += on_click

        self.button_play = WinForms.Button()
        self.button_play.Text = "Play"
        self.button_play.Anchor = WinForms.AnchorStyles.Left | WinForms.AnchorStyles.Top
        self.panel.Controls.Add(self.button_play, 0, 1)
        self.button_play.Click += self.play_pause

        self.button_stop = WinForms.Button()
        self.button_stop.Text = "Stop"
        self.button_stop.Anchor = WinForms.AnchorStyles.Left | WinForms.AnchorStyles.Top
        self.panel.Controls.Add(self.button_stop, 1, 1)
        self.button_stop.Click += self.stop

        self.trackbar_volume = WinForms.TrackBar()
        self.trackbar_volume.Maximum = 100
        self.trackbar_volume.Anchor = WinForms.AnchorStyles.Right | WinForms.AnchorStyles.Top
        self.trackbar_volume.AutoSize = False
        self.trackbar_volume.Height = 20
        self.trackbar_volume.TickStyle = getattr(WinForms.TickStyle, 'None')
        self.trackbar_volume.Value = INITIAL_VOLUME
        self.panel.Controls.Add(self.trackbar_volume, 2, 1)
        self.trackbar_volume.Scroll += lambda *_: self.set_volume(self.trackbar_volume.Value)

        def on_click(sender, args):
            w = self.trackbar_volume.Width - 28
            x = args.X - 14
            pos = max(0, min(100, int(x / w * 100)))
            self.trackbar_volume.Value = pos
            self.set_volume(pos)

        self.trackbar_volume.MouseDown += on_click

        self.ResumeLayout(False)
        self.PerformLayout()

    def open_file(self, *_):
        ofd = WinForms.OpenFileDialog()
        ofd.Filter = "All Files (*.*)|*.*"
        ofd.RestoreDirectory = True
        if ofd.ShowDialog() != WinForms.DialogResult.OK:
            return
        self.load_file(ofd.FileName)

    def load_file(self, filename):
        if self.mediaplayer.has_media():
            self.close_file()
        ok = self.mediaplayer.load_media_file(filename)
        if ok:
            self.media_duration = self.mediaplayer.get_duration()
            self.play_pause()
            self.Text = os.path.basename(filename)
            # media_duration would be 0 e.g. for HLS livestreams, where seeking is impossible
            self.trackbar_position.Enabled = self.media_duration > 0

    def close_file(self, *_):
        """Close/unload current media file
        """
        self.stop()
        self.mediaplayer.close_file()
        self.trackbar_position.Enabled = False
        self.Text = "Media Player"

    def play_pause(self, *_):
        """Toggle play/pause status"""
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.button_play.Text = "Play"
            self.timer.Stop()
            self.is_paused = True
        else:
            if not self.mediaplayer.has_media():
                return self.open_file()
            self.mediaplayer.play()
            self.button_play.Text = "Pause"
            self.timer.Start()
            self.is_paused = False

    def stop(self, *_):
        """Stop player"""
        self.mediaplayer.stop()
        self.timer.Stop()
        self.button_play.Text = "Play"
        self.trackbar_position.Value = 0

    def quit(self, *_):
        WinForms.Application.Exit()

    def set_volume(self, volume):
        """Set the volume"""
        self.mediaplayer.set_volume(volume / 100)

    def set_position(self, pos):
        """Set the media time according to the time slider"""
        self.mediaplayer.set_time(self.media_duration * pos / 2000.0)

    def update_ui(self, *_):
        """Update the time slider according to the current media time.
        """
        val = int(self.mediaplayer.get_time() / self.media_duration * 2000)
        self.trackbar_position.Value = val
        # No need for a timer if nothing is played
        if not self.mediaplayer.is_playing():
            self.timer.Stop()
            if not self.is_paused:
                self.stop()


def app_thread():
    main = Main()
    WinForms.Application.Run(main)
    main.Dispose()

if __name__ == "__main__":
    thread = Thread(ThreadStart(app_thread))
    thread.SetApartmentState(ApartmentState.STA)
    thread.Start()
    thread.Join()
