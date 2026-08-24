"""
Tkinter front-end for connect.py

Main window   -> single "Name" field for apprentices, calls connectApprentice(name, "")
Advanced menu -> username / password / host / volume fields, calls connect(...)

A system tray icon shows connection status (green = connected, red = not
connected). Right-clicking it lets you close the active connection or exit
the app.

Requires:
    pip install pystray pillow
(tkinter ships with standard Python on Windows)

also gonna be bundled so who cares
"""

import threading
import queue
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageDraw
import pystray

import connect  # the connection module


# shared state

class AppState:
    def __init__(self):
        self.process = None  # subprocess.Popen or None
        self.busy = False    # True while a connect attempt is in flight

    def set_process(self, proc):
        self.process = proc

    def is_connected(self):
        if self.process is None:
            return False
        return self.process.poll() is None


state = AppState()

# thread-safe channel for background work to report results back to the UI thread
result_queue = queue.Queue()

# reference to the advanced window's Connect button, if that window is open
# (used so we can enable/disable it alongside the simple button). None when closed.
advanced_submit_btn = None


# tray icon

def make_dot_icon(color):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 8
    draw.ellipse((margin, margin, size - margin, size - margin), fill=color)
    return img


ICON_RED = make_dot_icon("#d33")
ICON_GREEN = make_dot_icon("#3a3")

tray_icon = None  # pystray.Icon, created in main()


def refresh_tray():
    if tray_icon is None:
        return
    if state.is_connected():
        tray_icon.icon = ICON_GREEN
        tray_icon.title = "File Server Client - Connected"
    else:
        tray_icon.icon = ICON_RED
        tray_icon.title = "File Server Client - Not connected"
    # Force the menu to re-evaluate the "enabled" state of Close Connection
    tray_icon.update_menu()


def tray_close_connection(icon, item):
    terminate_mount()
    refresh_tray()


def terminate_mount():
    """Stop the active rclone mount, if any. Safe to call multiple times.

    Tries a normal terminate() first and gives it a few seconds to exit
    cleanly, then escalates to kill() if it's still hanging around. note that
    on Windows, Popen.terminate() is a hard TerminateProcess call (there's
    no real SIGTERM), so this is about as graceful as we can be without
    changing how connect.py spawns the process (like a CTRL_BREAK-capable
    process group + rclone's own unmount signal handling). I don't really care though
    """
    proc = state.process
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    state.set_process(None)


def tray_exit(icon, item):
    terminate_mount()
    icon.stop()
    root.after(0, root.destroy)


def tray_show_window(icon=None, item=None):
    # called from the tray thread hop back onto the Tk main thread to touch the UI
    def _show():
        root.deiconify()
        root.lift()
        root.focus_force()
    root.after(0, _show)


def build_tray_icon():
    menu = pystray.Menu(
        pystray.MenuItem("Open", tray_show_window, default=True),
        pystray.MenuItem(
            "Close Connection",
            tray_close_connection,
            enabled=lambda item: state.is_connected(),
        ),
        pystray.MenuItem("Exit", tray_exit),
    )
    icon = pystray.Icon("fileserver-client", ICON_RED, "File Server Client - Not connected", menu)
    return icon


# background worker helpers

def set_buttons_state(tk_state):
    try:
        simple_submit_btn.config(state=tk_state)
    except tk.TclError:
        pass
    if advanced_submit_btn is not None:
        try:
            advanced_submit_btn.config(state=tk_state)
        except tk.TclError:
            pass  # advanced window was closed


def run_in_background(target, *args):
    state.busy = True
    set_buttons_state("disabled")
    set_status_label()

    def worker():
        try:
            result = target(*args)
        except Exception as exc:
            result = exc
        result_queue.put(result)

    threading.Thread(target=worker, daemon=True).start()


def poll_result_queue():
    try:
        result = result_queue.get_nowait()
    except queue.Empty:
        result = None

    if result is not None:
        handle_connect_result(result)

    root.after(200, poll_result_queue)


def periodic_check():
    refresh_tray()
    set_status_label()
    root.after(2000, periodic_check)


def handle_connect_result(result):
    state.busy = False
    set_buttons_state("normal")

    if isinstance(result, Exception):
        messagebox.showerror("Connection failed", f"An error occurred:\n{result}")
    elif isinstance(result, int):
        # connect() returns 1 (int) on failure (e.g. host didn't resolve)
        messagebox.showerror("Connection failed", "Could not connect. Check the hostname and try again.")
    else:
        # Otherwise we got a Popen object back, success
        state.set_process(result)
        messagebox.showinfo("Connected", "Connection established.")

    refresh_tray()
    set_status_label()


# Main window

def confirm_reconnect_if_needed():
    """If already busy, tell the user to wait. If already connected, confirm
    before dropping that connection to start a new one. Returns True if it's
    OK to proceed with a new connect attempt."""
    if state.busy:
        messagebox.showinfo("Please wait", "Already connecting - please wait for that to finish.")
        return False
    if state.is_connected():
        proceed = messagebox.askyesno(
            "Already connected",
            "You're already connected. Disconnect the current session and start a new one?",
        )
        if not proceed:
            return False
        terminate_mount()
        refresh_tray()
        set_status_label()
    return True


def submit_simple():
    name = simple_name_var.get().strip()
    if not name:
        messagebox.showwarning("Name required", "Please enter your name.")
        return
    if not confirm_reconnect_if_needed():
        return
    run_in_background(connect.connectApprentice, name, "")


def set_status_label():
    if state.busy:
        status_var.set("Status: Connecting...")
        status_label.config(foreground="#a67c00")
    elif state.is_connected():
        status_var.set("Status: Connected")
        status_label.config(foreground="#227722")
    else:
        status_var.set("Status: Not connected")
        status_label.config(foreground="#993333")


# Advanced window

PLACEHOLDER = "leave empty for default"
PLACEHOLDER_COLOR = "grey"
NORMAL_COLOR = "black"


def add_placeholder(entry, text):
    entry.insert(0, text)
    entry.config(foreground=PLACEHOLDER_COLOR)

    def on_focus_in(_event):
        if entry.get() == text and str(entry.cget("foreground")) == PLACEHOLDER_COLOR:
            entry.delete(0, tk.END)
            entry.config(foreground=NORMAL_COLOR)

    def on_focus_out(_event):
        if not entry.get():
            entry.insert(0, text)
            entry.config(foreground=PLACEHOLDER_COLOR)

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def get_real_value(entry, placeholder_text):
    """Return '' if the entry is still showing its placeholder, else its value."""
    val = entry.get()
    if val == placeholder_text and str(entry.cget("foreground")) == PLACEHOLDER_COLOR:
        return ""
    return val


def open_advanced_window():
    global advanced_submit_btn

    win = tk.Toplevel(root)
    win.title("Advanced Connection")
    win.resizable(False, False)

    def on_advanced_close():
        global advanced_submit_btn
        advanced_submit_btn = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_advanced_close)

    frame = ttk.Frame(win, padding=16)
    frame.grid(row=0, column=0, sticky="nsew")

    ttk.Label(frame, text="Username:").grid(row=0, column=0, sticky="w", pady=4)
    username_entry = ttk.Entry(frame, width=30)
    username_entry.grid(row=0, column=1, pady=4)

    ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky="w", pady=4)
    password_entry = ttk.Entry(frame, width=30, show="*")
    password_entry.grid(row=1, column=1, pady=4)

    ttk.Label(frame, text="Host:").grid(row=2, column=0, sticky="w", pady=4)
    host_entry = ttk.Entry(frame, width=30)
    host_entry.grid(row=2, column=1, pady=4)
    add_placeholder(host_entry, PLACEHOLDER)

    ttk.Label(frame, text="Volume:").grid(row=3, column=0, sticky="w", pady=4)
    volume_entry = ttk.Entry(frame, width=30)
    volume_entry.grid(row=3, column=1, pady=4)
    add_placeholder(volume_entry, PLACEHOLDER)

    def submit_advanced():
        username = username_entry.get().strip()
        password = password_entry.get()
        host = get_real_value(host_entry, PLACEHOLDER).strip()
        volume = get_real_value(volume_entry, PLACEHOLDER).strip()

        if not username:
            messagebox.showwarning("Username required", "Please enter a username.", parent=win)
            return
        if not confirm_reconnect_if_needed():
            return

        run_in_background(connect.connect, username, password, host, volume)

    submit_btn = ttk.Button(frame, text="Connect", command=submit_advanced)
    submit_btn.grid(row=4, column=0, columnspan=2, pady=(12, 0))
    advanced_submit_btn = submit_btn

    # in case this window was opened while a connect was already in flight
    if state.busy:
        submit_btn.config(state="disabled")


# Build main window

root = tk.Tk()
root.title("File Server Client")
root.resizable(False, False)

main_frame = ttk.Frame(root, padding=20)
main_frame.grid(row=0, column=0, sticky="nsew")

ttk.Label(main_frame, text="Enter your name to connect:").grid(row=0, column=0, columnspan=2, pady=(0, 8))

simple_name_var = tk.StringVar()
simple_name_entry = ttk.Entry(main_frame, textvariable=simple_name_var, width=28)
simple_name_entry.grid(row=1, column=0, columnspan=2, pady=(0, 12))
simple_name_entry.focus()
simple_name_entry.bind("<Return>", lambda _e: submit_simple())

simple_submit_btn = ttk.Button(main_frame, text="Connect", command=submit_simple)
simple_submit_btn.grid(row=2, column=0, columnspan=2, pady=(0, 16))

status_var = tk.StringVar(value="Status: Not connected")
status_label = ttk.Label(main_frame, textvariable=status_var)
status_label.grid(row=3, column=0, columnspan=2, pady=(0, 4))

# advanced options tucked away in the corner, out of the way for the children
advanced_link = ttk.Label(main_frame, text="Advanced options", foreground="#4444aa", cursor="hand2", font=("TkDefaultFont", 8, "underline"))
advanced_link.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
advanced_link.bind("<Button-1>", lambda _e: open_advanced_window())


def on_window_close():
    # Hide to tray instead of quitting outright, the mount stays alive and
    # can be reopened from the tray icon. Use tray "Exit" to actually quit
    # (which terminates the mount).
    root.withdraw()


root.protocol("WM_DELETE_WINDOW", on_window_close)

# no matter how the process ends (tray Exit, Ctrl+C, etc.),
# make sure we don't leave an orphaned rclone mount running.
import atexit
atexit.register(terminate_mount)

# Entry point

def main():
    global tray_icon
    tray_icon = build_tray_icon()

    # pystray's icon.run() is blocking, so it gets its own thread
    # Tk's mainloop stays on the main thread
    threading.Thread(target=tray_icon.run, daemon=True).start()

    root.after(200, poll_result_queue)
    root.after(2000, periodic_check)
    root.mainloop()


if __name__ == "__main__":
    main()
