"""Minimal tkinter desktop interface for Proton Duplicate Launcher."""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from typing import List, Optional, Sequence

from .backend import (
    ProcessCandidate,
    build_clone_prefix_suggestion,
    candidate_display_name,
    launch_second_instance,
    list_candidates,
    user_facing_candidates,
)

GUI_EXIT_CODE = 3


def shorten_text(text: str, max_length: int) -> str:
    """Shorten long text for compact GUI display."""

    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


class LauncherApp:
    """Minimal desktop UI for the Proton duplicate launcher."""

    def __init__(self, root, tk_module, ttk_module, filedialog_module, messagebox_module):
        self.root = root
        self.tk = tk_module
        self.ttk = ttk_module
        self.filedialog = filedialog_module
        self.messagebox = messagebox_module

        self.queue: queue.Queue = queue.Queue()
        self.candidates: List[ProcessCandidate] = []
        self.busy = False

        self.exe_override_var = self.tk.StringVar()
        self.clone_prefix_enabled_var = self.tk.BooleanVar(value=False)
        self.clone_prefix_var = self.tk.StringVar()
        self.status_var = self.tk.StringVar(
            value="Start your game in Steam, then click Refresh."
        )
        self.selected_name_var = self.tk.StringVar(value="No game selected")
        self.selected_exe_var = self.tk.StringVar(value="Not detected yet")
        self.selected_prefix_var = self.tk.StringVar(value="Not detected yet")

        self.refresh_button = None
        self.preview_button = None
        self.launch_button = None
        self.exe_browse_button = None
        self.exe_clear_button = None
        self.clone_checkbutton = None
        self.clone_browse_button = None
        self.clone_reset_button = None
        self.clone_entry = None
        self.process_tree = None
        self.log_text = None

        self.configure_window()
        self.build_ui()
        self.root.after(125, self.process_worker_queue)
        self.log(
            "Welcome. Start the first copy of your game in Steam, then click Refresh."
        )
        self.refresh_candidates()

    def configure_window(self) -> None:
        """Apply basic window settings and a light default theme."""

        self.root.title("Proton Duplicate Launcher")
        self.root.geometry("1080x760")
        self.root.minsize(900, 640)

        style = self.ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Noto Sans", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("Noto Sans", 10))
        style.configure("Value.TLabel", font=("Noto Sans", 10, "bold"))
        style.configure("Treeview", rowheight=28)

    def build_ui(self) -> None:
        """Create the desktop layout."""

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = self.ttk.Frame(self.root, padding=16)
        container.grid(sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)
        container.rowconfigure(5, weight=1)

        header = self.ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        self.ttk.Label(
            header,
            text="Proton Duplicate Launcher",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.ttk.Label(
            header,
            text=(
                "1. Start your game in Steam. 2. Click Refresh. "
                "3. Select the game. 4. Preview or launch the second copy."
            ),
            style="Subtitle.TLabel",
            wraplength=760,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        actions = self.ttk.Frame(container)
        actions.grid(row=1, column=0, sticky="ew", pady=(14, 14))
        actions.columnconfigure(3, weight=1)

        self.refresh_button = self.ttk.Button(
            actions,
            text="Refresh",
            command=self.refresh_candidates,
        )
        self.refresh_button.grid(row=0, column=0, sticky="w")

        self.preview_button = self.ttk.Button(
            actions,
            text="Preview Launch",
            command=lambda: self.start_launch(dry_run=True),
        )
        self.preview_button.grid(row=0, column=1, sticky="w", padx=(8, 0))

        self.launch_button = self.ttk.Button(
            actions,
            text="Launch Second Copy",
            command=lambda: self.start_launch(dry_run=False),
        )
        self.launch_button.grid(row=0, column=2, sticky="w", padx=(8, 0))

        self.ttk.Label(
            actions,
            textvariable=self.status_var,
            style="Subtitle.TLabel",
            anchor="e",
            justify="right",
        ).grid(row=0, column=3, sticky="e")

        list_frame = self.ttk.LabelFrame(container, text="Running Games", padding=12)
        list_frame.grid(row=2, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        columns = ("game", "pid", "prefix")
        self.process_tree = self.ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.process_tree.heading("game", text="Game")
        self.process_tree.heading("pid", text="PID")
        self.process_tree.heading("prefix", text="Steam Prefix")
        self.process_tree.column("game", width=240, anchor="w")
        self.process_tree.column("pid", width=90, anchor="center")
        self.process_tree.column("prefix", width=560, anchor="w")
        self.process_tree.grid(row=0, column=0, sticky="nsew")
        self.process_tree.bind("<<TreeviewSelect>>", self.on_selection_changed)

        list_scrollbar = self.ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.process_tree.yview,
        )
        list_scrollbar.grid(row=0, column=1, sticky="ns")
        self.process_tree.configure(yscrollcommand=list_scrollbar.set)

        details_frame = self.ttk.LabelFrame(container, text="Selected Game", padding=12)
        details_frame.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        details_frame.columnconfigure(1, weight=1)

        self.ttk.Label(details_frame, text="Game").grid(row=0, column=0, sticky="w")
        self.ttk.Label(
            details_frame,
            textvariable=self.selected_name_var,
            style="Value.TLabel",
            wraplength=800,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.ttk.Label(details_frame, text="Detected EXE").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        self.ttk.Label(
            details_frame,
            textvariable=self.selected_exe_var,
            wraplength=800,
        ).grid(row=1, column=1, sticky="w", padx=(10, 0), pady=(8, 0))

        self.ttk.Label(details_frame, text="Steam Prefix").grid(
            row=2, column=0, sticky="w", pady=(8, 0)
        )
        self.ttk.Label(
            details_frame,
            textvariable=self.selected_prefix_var,
            wraplength=800,
        ).grid(row=2, column=1, sticky="w", padx=(10, 0), pady=(8, 0))

        options_frame = self.ttk.LabelFrame(container, text="Optional Settings", padding=12)
        options_frame.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        options_frame.columnconfigure(1, weight=1)

        self.ttk.Label(
            options_frame,
            text="If the game was detected wrong, choose the .exe manually.",
        ).grid(row=0, column=0, columnspan=4, sticky="w")

        self.ttk.Label(options_frame, text="Game EXE").grid(
            row=1, column=0, sticky="w", pady=(10, 0)
        )
        exe_entry = self.ttk.Entry(
            options_frame,
            textvariable=self.exe_override_var,
        )
        exe_entry.grid(row=1, column=1, sticky="ew", pady=(10, 0), padx=(10, 0))

        self.exe_browse_button = self.ttk.Button(
            options_frame,
            text="Browse...",
            command=self.browse_executable,
        )
        self.exe_browse_button.grid(row=1, column=2, sticky="w", padx=(8, 0), pady=(10, 0))

        self.exe_clear_button = self.ttk.Button(
            options_frame,
            text="Clear",
            command=lambda: self.exe_override_var.set(""),
        )
        self.exe_clear_button.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        self.clone_checkbutton = self.ttk.Checkbutton(
            options_frame,
            text="Use a separate copied prefix for the second copy",
            variable=self.clone_prefix_enabled_var,
            command=self.on_clone_prefix_toggle,
        )
        self.clone_checkbutton.grid(row=2, column=0, columnspan=4, sticky="w", pady=(14, 0))

        self.ttk.Label(
            options_frame,
            text="The app creates this folder for you. Pick a new location if you want one.",
            style="Subtitle.TLabel",
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(6, 0))

        self.ttk.Label(options_frame, text="Copied Prefix").grid(
            row=4, column=0, sticky="w", pady=(10, 0)
        )
        self.clone_entry = self.ttk.Entry(
            options_frame,
            textvariable=self.clone_prefix_var,
        )
        self.clone_entry.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=(10, 0))

        self.clone_browse_button = self.ttk.Button(
            options_frame,
            text="Choose Location...",
            command=self.browse_clone_prefix,
        )
        self.clone_browse_button.grid(row=4, column=2, sticky="w", padx=(8, 0), pady=(10, 0))

        self.clone_reset_button = self.ttk.Button(
            options_frame,
            text="Use Suggested",
            command=self.reset_clone_prefix_suggestion,
        )
        self.clone_reset_button.grid(row=4, column=3, sticky="w", padx=(8, 0), pady=(10, 0))

        log_frame = self.ttk.LabelFrame(container, text="Activity", padding=12)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(14, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = self.tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            relief="flat",
            borderwidth=0,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_scrollbar = self.ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.update_button_states()
        self.update_clone_prefix_state()

    def log(self, message: str) -> None:
        """Append a message to the activity box."""

        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def update_button_states(self) -> None:
        """Enable or disable controls based on the current state."""

        selected = self.get_selected_candidate() is not None
        launch_state = "disabled" if self.busy or not selected else "normal"
        normal_state = "disabled" if self.busy else "normal"

        self.refresh_button.configure(state=normal_state)
        self.preview_button.configure(state=launch_state)
        self.launch_button.configure(state=launch_state)
        self.exe_browse_button.configure(state=normal_state)
        self.exe_clear_button.configure(state=normal_state)
        self.clone_checkbutton.configure(state=normal_state)
        self.update_clone_prefix_state()

    def update_clone_prefix_state(self) -> None:
        """Enable or disable the clone-prefix widgets."""

        enabled = self.clone_prefix_enabled_var.get() and not self.busy
        state = "normal" if enabled else "disabled"

        self.clone_entry.configure(state=state)
        self.clone_browse_button.configure(state=state)
        self.clone_reset_button.configure(state=state)

    def set_busy(self, busy: bool, status_message: str) -> None:
        """Set the busy state and refresh the UI controls."""

        self.busy = busy
        self.status_var.set(status_message)
        self.update_button_states()

    def get_selected_candidate(self) -> Optional[ProcessCandidate]:
        """Return the currently selected process candidate."""

        selection = self.process_tree.selection()
        if not selection:
            return None

        selected_pid = int(selection[0])
        for candidate in self.candidates:
            if candidate.pid == selected_pid:
                return candidate
        return None

    def fill_candidate_list(self, candidates: Sequence[ProcessCandidate]) -> None:
        """Refresh the list widget with the detected games."""

        current_selection = self.process_tree.selection()
        selected_pid = current_selection[0] if current_selection else None

        self.process_tree.delete(*self.process_tree.get_children())
        self.candidates = list(candidates)

        for candidate in self.candidates:
            prefix_text = shorten_text(candidate.compat_data_path or "", 64)
            self.process_tree.insert(
                "",
                "end",
                iid=str(candidate.pid),
                values=(
                    candidate_display_name(candidate),
                    candidate.pid,
                    prefix_text,
                ),
            )

        if selected_pid and self.process_tree.exists(selected_pid):
            self.process_tree.selection_set(selected_pid)
        elif self.candidates:
            self.process_tree.selection_set(str(self.candidates[0].pid))

        self.update_selected_details()

    def update_selected_details(self) -> None:
        """Refresh the detail labels for the selected game."""

        candidate = self.get_selected_candidate()
        if candidate is None:
            self.selected_name_var.set("No game selected")
            self.selected_exe_var.set("Not detected yet")
            self.selected_prefix_var.set("Not detected yet")
            self.update_button_states()
            return

        self.selected_name_var.set(candidate_display_name(candidate))
        self.selected_exe_var.set(candidate.exe_hint or "Could not detect automatically")
        self.selected_prefix_var.set(candidate.compat_data_path or "Not available")
        self.update_button_states()

    def on_selection_changed(self, _event=None) -> None:
        """React to a new selected game in the list."""

        self.update_selected_details()
        if self.clone_prefix_enabled_var.get():
            self.reset_clone_prefix_suggestion(force=False)

    def on_clone_prefix_toggle(self) -> None:
        """Enable or disable separate-prefix mode."""

        if self.clone_prefix_enabled_var.get() and not self.clone_prefix_var.get().strip():
            self.reset_clone_prefix_suggestion(force=True)
        self.update_clone_prefix_state()

    def reset_clone_prefix_suggestion(self, force: bool = True) -> None:
        """Restore the suggested clone-prefix location for the selected game."""

        candidate = self.get_selected_candidate()
        if candidate is None:
            if force:
                self.clone_prefix_var.set("")
            return

        if not force and self.clone_prefix_var.get().strip():
            return

        suggestion = build_clone_prefix_suggestion(candidate)
        self.clone_prefix_var.set(str(suggestion))

    def browse_executable(self) -> None:
        """Open a file chooser for a manual game executable override."""

        filename = self.filedialog.askopenfilename(
            title="Choose the game executable",
            filetypes=(
                ("Windows programs", "*.exe *.bat *.msi"),
                ("All files", "*"),
            ),
        )
        if filename:
            self.exe_override_var.set(filename)

    def browse_clone_prefix(self) -> None:
        """Choose where the copied prefix should be created."""

        current_value = self.clone_prefix_var.get().strip()
        if current_value:
            current_path = Path(current_value).expanduser()
            initial_directory = (
                current_path.parent if current_path.parent.exists() else Path.home()
            )
            folder_name = current_path.name
        else:
            initial_directory = Path.home()
            folder_name = "game-second"

        selected_directory = self.filedialog.askdirectory(
            title="Choose where the copied prefix should be created",
            initialdir=str(initial_directory),
            mustexist=True,
        )
        if selected_directory:
            self.clone_prefix_var.set(str(Path(selected_directory) / folder_name))

    def refresh_candidates(self) -> None:
        """Refresh the detected game list in a background thread."""

        if self.busy:
            return

        self.set_busy(True, "Looking for running Proton games...")
        threading.Thread(target=self.worker_refresh_candidates, daemon=True).start()

    def worker_refresh_candidates(self) -> None:
        """Background worker for process discovery."""

        try:
            candidates = user_facing_candidates(list_candidates())
            self.queue.put(("refresh_complete", candidates))
        except Exception as exc:  # pragma: no cover
            self.queue.put(("error", f"Could not scan running games: {exc}"))

    def start_launch(self, dry_run: bool) -> None:
        """Start a preview or real launch operation."""

        candidate = self.get_selected_candidate()
        if candidate is None:
            self.messagebox.showwarning(
                "Select a game",
                "Pick the running game you want to duplicate first.",
            )
            return

        exe_override = self.exe_override_var.get().strip() or None
        clone_prefix_to = None
        if self.clone_prefix_enabled_var.get():
            clone_prefix_to = self.clone_prefix_var.get().strip()
            if not clone_prefix_to:
                self.messagebox.showwarning(
                    "Choose a copied prefix location",
                    "Turn off the copied prefix option or choose where the new copy should be created.",
                )
                return

        if not dry_run:
            confirmed = self.messagebox.askyesno(
                "Launch second copy?",
                (
                    f"Start another copy of {candidate_display_name(candidate)} now?\n\n"
                    "Use Preview Launch first if you want to check the detected settings."
                ),
            )
            if not confirmed:
                return

        action_text = (
            "Previewing launch settings..." if dry_run else "Launching second copy..."
        )
        self.set_busy(True, action_text)
        self.log(action_text)

        thread = threading.Thread(
            target=self.worker_launch,
            args=(candidate.pid, exe_override, clone_prefix_to, dry_run),
            daemon=True,
        )
        thread.start()

    def worker_launch(
        self,
        pid: int,
        exe_override: Optional[str],
        clone_prefix_to: Optional[str],
        dry_run: bool,
    ) -> None:
        """Background worker for preview and launch operations."""

        messages: List[str] = []
        try:
            result = launch_second_instance(
                pid=pid,
                exe_override=exe_override,
                clone_prefix_to=clone_prefix_to,
                dry_run=dry_run,
                reporter=messages.append,
            )
            self.queue.put(("launch_complete", result, dry_run, messages))
        except Exception as exc:
            self.queue.put(("launch_failed", str(exc), dry_run, messages))

    def process_worker_queue(self) -> None:
        """Drain queued background-worker updates on the Tk event loop."""

        while True:
            try:
                event = self.queue.get_nowait()
            except queue.Empty:
                break

            event_name = event[0]

            if event_name == "refresh_complete":
                candidates = event[1]
                self.fill_candidate_list(candidates)
                self.set_busy(False, "Ready")
                if candidates:
                    count = len(candidates)
                    self.log(
                        f"Found {count} running game{'s' if count != 1 else ''}. Select one and launch when ready."
                    )
                else:
                    self.log(
                        "No running Proton game was found. Start the first copy from Steam, then click Refresh again."
                    )

            elif event_name == "launch_complete":
                _result, dry_run, messages = event[1], event[2], event[3]
                for message in messages:
                    self.log(message)
                self.set_busy(False, "Ready")

                if dry_run:
                    self.log(
                        "Preview finished. If the details look right, click Launch Second Copy."
                    )
                else:
                    self.log("The second copy was started.")
                    self.messagebox.showinfo(
                        "Second copy started",
                        "The second copy was launched. If nothing appears right away, check the Activity box below.",
                    )
                    self.refresh_candidates()

            elif event_name == "launch_failed":
                error_message, _dry_run, messages = event[1], event[2], event[3]
                for message in messages:
                    self.log(message)
                self.set_busy(False, "Ready")
                self.log(f"Error: {error_message}")
                self.messagebox.showerror("Launch failed", error_message)

            elif event_name == "error":
                error_message = event[1]
                self.set_busy(False, "Ready")
                self.log(f"Error: {error_message}")
                self.messagebox.showerror("Error", error_message)

        self.root.after(125, self.process_worker_queue)


def launch_gui() -> int:
    """Start the minimal desktop interface."""

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:
        print(
            "Error: Tkinter is not available in this Python installation, so the GUI cannot be opened.",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return GUI_EXIT_CODE

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(
            "Error: Could not open the desktop window. If you are on a headless session, use the CLI commands instead.",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return GUI_EXIT_CODE

    LauncherApp(root, tk, ttk, filedialog, messagebox)
    root.mainloop()
    return 0
