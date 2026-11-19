#!/usr/bin/env python3
"""Run the SmartSeal dashboard and gateway as one managed application."""

import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
SHUTDOWN_TIMEOUT_SECONDS = 20
POLL_INTERVAL_SECONDS = 0.25

_stop_requested = False


def _request_stop(_signum, _frame):
    global _stop_requested
    _stop_requested = True


def _signal_child_to_stop(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)
    except (OSError, ValueError):
        # If graceful signalling is unavailable, the timeout path below
        # escalates to terminate and then kill.
        pass


def _stop_children(processes):
    for process in processes:
        _signal_child_to_stop(process)

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
    for process in processes:
        remaining = max(0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.terminate()

    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def _start_processes():
    commands = (
        ("dashboard", "Dashboard/dashboard.py"),
        ("gateway", "Gateway/XIAO/gateway_main.py"),
    )
    processes = []

    for name, script in commands:
        options = {"cwd": ROOT}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            options["start_new_session"] = True

        print(f"Starting {name}: {script}", flush=True)
        process = subprocess.Popen([sys.executable, script], **options)
        processes.append(process)

    return processes


def main():
    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)

    processes = []
    exit_code = 0
    try:
        processes = _start_processes()
        print("Dashboard and gateway are running. Press Ctrl+C to stop both.", flush=True)

        while not _stop_requested:
            for name, process in zip(("dashboard", "gateway"), processes):
                code = process.poll()
                if code is not None:
                    print(f"{name} exited with code {code}; stopping the other program.")
                    exit_code = code
                    _request_stop(None, None)
                    break
            time.sleep(POLL_INTERVAL_SECONDS)
    except OSError as error:
        print(f"Could not start SmartSeal: {error}", file=sys.stderr)
        exit_code = 1
    finally:
        if processes:
            print("Stopping dashboard and gateway...", flush=True)
            _stop_children(processes)

    if _stop_requested and exit_code == 0:
        print("SmartSeal stopped.", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
