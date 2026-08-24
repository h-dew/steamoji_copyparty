"""
File Server Client
-------------------
Simple Tkinter front-end for connect.py

Main window   -> single "Name" field for apprentices, calls connectApprentice(name, "")
Advanced menu -> username / password / host / volume fields, calls connect(...)

A system tray icon shows connection status (green = connected, red = not
connected). Right-clicking it lets you close the active connection or exit
the app.

Requires:
    pip install pystray pillow
(tkinter ships with standard Python on Windows)
"""

import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageDraw
import pystray

import connect  # your connect.py module


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

class AppState:
    """Holds the current mount subprocess so the tray icon / UI can react."""
    def __init__(self):
        self.process = None  # subprocess.Popen or None

    def set_process(self, proc):
        self.process = proc

    def is_connected(self):
        # Popen objects are truthy; also check the process hasn't exited
        if self.process is None:
            return False
        return self.process.poll() is None


state = AppState()

# Thread-safe channel for background work to report results back to the UI thread
result_queue = queue.Queue()


# ---------------------------------------------------------------------------
# Tray icon
# ---------------------------------------------------------------------------

def make_dot_icon(color):
    """Draw a simple colored circle as the tray icon (no external icon files needed)."""
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
    """Update tray icon color/title/menu to match current connection state."""
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
    if state.is_connected():
        try:
            state.process.terminate()
        except Exception:
            pass
        state.set_process(None)
        refresh_tray()


def tray_exit(icon, item):
    if state.is_connected():
        try:
            state.process.terminate()
        except Exception:
            pass
    icon.stop()
    root.after(0, root.destroy)


def build_tray_icon():
    menu = pystray.Menu(
        pystray.MenuItem(
            "Close Connection",
            tray_close_connection,
            enabled=lambda item: state.is_connected(),
        ),
        pystray.MenuItem("Exit", tray_exit),
    )
    icon = pystray.Icon("fileserver-client", ICON_RED, "File Server Client - Not connected", menu)
    return icon


# ---------------------------------------------------------------------------
# Background worker helpers
# ---------------------------------------------------------------------------

def run_in_background(target, *args):
    """Run a connect.py call off the UI thread, since it may shell out to
    winget / rclone and block for a while."""
    def worker():
        try:
            result = target(*args)
        except Exception as exc:
            result = exc
        result_queue.put(result)

    threading.Thread(target=worker, daemon=True).start()


def poll_result_queue():
    """Runs on the Tk main loop; checks for background results periodically."""
    try:
        result = result_queue.get_nowait()
    except queue.Empty:
        result = None

    if result is not None:
        handle_connect_result(result)

    root.after(200, poll_result_queue)


def handle_connect_result(result):
    if isinstance(result, Exception):
        messagebox.showerror("Connection failed", f"An error occurred:\n{result}")
    elif isinstance(result, int):
        # connect() returns 1 (int) on failure (e.g. host didn't resolve)
        messagebox.showerror("Connection failed", "Could not connect. Check the hostname and try again.")
    else:
        # Otherwise we got a Popen object back -> success
        state.set_process(result)
        messagebox.showinfo("Connected", "Connection established.")

    refresh_tray()
    set_status_label()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

def submit_simple():
    name = simple_name_var.get().strip()
    if not name:
        messagebox.showwarning("Name required", "Please enter your name.")
        return
    simple_submit_btn.config(state="disabled")
    root.after(100, lambda: simple_submit_btn.config(state="normal"))
    run_in_background(connect.connectApprentice, name, "")


def set_status_label():
    if state.is_connected():
        status_var.set("Status: Connected")
        status_label.config(foreground="#227722")
    else:
        status_var.set("Status: Not connected")
        status_label.config(foreground="#993333")


# --- Advanced window ---------------------------------------------------

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
    win = tk.Toplevel(root)
    win.title("Advanced Connection")
    win.resizable(False, False)

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

        submit_btn.config(state="disabled")
        win.after(100, lambda: submit_btn.config(state="normal"))
        run_in_background(connect.connect, username, password, host, volume)

    submit_btn = ttk.Button(frame, text="Connect", command=submit_advanced)
    submit_btn.grid(row=4, column=0, columnspan=2, pady=(12, 0))


# ---------------------------------------------------------------------------
# Build main window
# ---------------------------------------------------------------------------

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

# Advanced options tucked away in the corner, out of the apprentices' way
advanced_link = ttk.Label(main_frame, text="Advanced options", foreground="#4444aa", cursor="hand2", font=("TkDefaultFont", 8, "underline"))
advanced_link.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))
advanced_link.bind("<Button-1>", lambda _e: open_advanced_window())


def on_window_close():
    # Hide to tray instead of quitting outright, so the mount stays alive
    root.withdraw()


root.protocol("WM_DELETE_WINDOW", on_window_close)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global tray_icon
    tray_icon = build_tray_icon()

    # pystray's icon.run() is blocking, so it gets its own thread;
    # Tk's mainloop stays on the main thread.
    threading.Thread(target=tray_icon.run, daemon=True).start()

    root.after(200, poll_result_queue)
    root.mainloop()


if __name__ == "__main__":
    main()
