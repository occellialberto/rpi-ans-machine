"""
player.py

Simple-to-use audio playback helper tailored for the Raspberry Pi.
The implementation tries several different playback back-ends, choosing
those that are most likely to be present on a Pi first (omxplayer, aplay),
but it will gracefully fall back to pure-python solutions if available.

Public helpers
--------------
play_audio(path: str, *, blocking: bool = True) -> bool
    Start playback of *path* through the
     default audio device.

stop_audio() -> bool
    Best-effort attempt to halt any currently playing audio that was started
    through this module (only effective for non-blocking playback).

play(path: str, *, blocking: bool = True) -> threading.Thread
    Convenience wrapper that starts a background thread running play_audio
    and returns the Thread instance.

Typical usage
-------------
>>> from player import play, stop
>>> th = play("/home/pi/sounds/beep.wav")  # fire-and-forget
>>> # …later …
>>> stop()        # stop it again

Environment variables recognised
--------------------------------
PI_AUDIO_OUTPUT   Choose audio output for omxplayer.
                  Allowed values: "local", "hdmi", "both"  (default "local")
"""

from __future__ import annotations

import os
import sys
import shutil
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable, Any, List, Tuple


# ---------------------------------------------------------------------------#
# Internals – keep track of non-blocking playbacks so we can stop them later #
# ---------------------------------------------------------------------------#
_PLAYBACK_HANDLES: List[Tuple[str, Any]] = []   # (backend identifier, handle)
_PLAYBACK_LOCK = threading.Lock()


def _register_playback(backend: str, handle: Any) -> None:
    """
    Remember a playback handle so that `stop_audio()` can later terminate it.
    """
    with _PLAYBACK_LOCK:
        _PLAYBACK_HANDLES.append((backend, handle))


def _is_handle_active(backend: str, handle: Any) -> bool:
    """
    Helper that returns True if the supplied handle is believed to be
    currently playing.
    """
    try:
        if backend in {"omxplayer", "aplay", "system"}:
            return handle.poll() is None
        if backend == "simpleaudio":
            return handle.is_playing()
        if backend == "pygame":
            return handle.get_busy()
    except Exception:
        return False
    return False


def stop_audio() -> bool:
    """
    Attempt to stop any audio that is still playing.

    Returns
    -------
    bool
        True if at least one playback was stopped, False otherwise.
    """
    stopped_any = False
    with _PLAYBACK_LOCK:
        # Work on a copy so we can modify the original list while iterating
        for backend, handle in _PLAYBACK_HANDLES[:]:
            try:
                if not _is_handle_active(backend, handle):
                    _PLAYBACK_HANDLES.remove((backend, handle))
                    continue

                if backend in {"omxplayer", "aplay", "system"}:
                    handle.terminate()
                    handle.wait(timeout=1)
                elif backend == "simpleaudio":
                    handle.stop()
                elif backend == "pygame":
                    handle.stop()
                # playsound threads cannot be stopped cleanly – ignore
                else:
                    continue
                stopped_any = True
            except Exception:
                # Ignore individual failures but keep processing others
                pass
            finally:
                # Drop handle if it no longer plays
                if not _is_handle_active(backend, handle):
                    try:
                        _PLAYBACK_HANDLES.remove((backend, handle))
                    except ValueError:
                        pass
    return stopped_any


# ---------------------------------------------------------------------------#
# Helpers                                                                     #
# ---------------------------------------------------------------------------#
def _is_raspberry_pi() -> bool:
    """
    Very lightweight test to check whether we are running on a Raspberry Pi.
    We look at /proc/device-tree/model which is present on modern Pi OS
    builds.  If that fails we assume we are *not* on a Pi.
    """
    try:
        with open("/proc/device-tree/model", "r") as fp:
            return "Raspberry Pi" in fp.read()
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Back-end #1 – omxplayer (preferred on Raspberry Pi, supports many formats)  #
# ---------------------------------------------------------------------------#
def _play_with_omxplayer(file_path: str, blocking: bool) -> bool:
    """
    Use omxplayer for playback.  It ships with Raspberry Pi OS by default and
    handles a wide variety of audio formats with hardware acceleration.
    """
    if not shutil.which("omxplayer"):
        return False

    audio_out = os.getenv("PI_AUDIO_OUTPUT", "local")  # local / hdmi / both
    cmd = ["omxplayer", "-o", audio_out, file_path]

    try:
        if blocking:
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
        else:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    start_new_session=True)
            _register_playback("omxplayer", proc)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Back-end #2 – aplay (ALSA, wav & raw files)                                 #
# ---------------------------------------------------------------------------#
def _play_with_aplay(file_path: str, blocking: bool) -> bool:
    """
    Plays WAV/RAW files through ALSA with aplay.  Suitable for very small
    systems where only .wav files are required.
    """
    if not shutil.which("aplay"):
        return False

    cmd = ["aplay", "-q", file_path]  # -q = quiet
    try:
        if blocking:
            subprocess.run(cmd, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True)
        else:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    start_new_session=True)
            _register_playback("aplay", proc)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Back-end #3 – simpleaudio (pure python, wav-only, cross-platform)           #
# ---------------------------------------------------------------------------#
def _play_with_simpleaudio(file_path: str, blocking: bool) -> bool:
    try:
        import simpleaudio  # type: ignore
    except (ImportError, ModuleNotFoundError):
        return False

    try:
        wave_obj = simpleaudio.WaveObject.from_wave_file(file_path)
        play_obj = wave_obj.play()
        if blocking:
            play_obj.wait_done()
        else:
            _register_playback("simpleaudio", play_obj)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Back-end #4 – pygame (commonly available on Pi OS)                          #
# ---------------------------------------------------------------------------#
def _play_with_pygame(file_path: str, blocking: bool) -> bool:
    try:
        import pygame  # type: ignore
    except (ImportError, ModuleNotFoundError):
        return False

    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        sound = pygame.mixer.Sound(file_path)
        channel = sound.play()
        if blocking:
            while channel.get_busy():
                pygame.time.wait(50)
        else:
            _register_playback("pygame", channel)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Back-end #5 – playsound (small external dependency, always blocking)        #
# ---------------------------------------------------------------------------#
def _play_with_playsound(file_path: str, blocking: bool) -> bool:
    try:
        from playsound import playsound  # type: ignore
    except (ImportError, ModuleNotFoundError):
        return False

    try:
        # playsound is blocking so we use a thread for non-blocking mode.
        if blocking:
            playsound(file_path)
        else:
            threading.Thread(target=playsound,
                             args=(file_path,), daemon=True).start()
            # playsound offers no stop mechanism, so we cannot register it
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------#
# Generic “system command” fallback (works on many platforms)                 #
# ---------------------------------------------------------------------------#
_OTHER_CMDS = {
    "darwin": ["afplay"],
    "linux": ["ffplay", "paplay"],
    "linux2": ["ffplay", "paplay"],
    "win32": ["powershell"],
}


def _build_system_command(cmd: str, file_path: str) -> Optional[List[str]]:
    """
    Build the concrete subprocess command for a given base command name.
    Handles special cases such as PowerShell on Windows and ffplay options.
    """
    if cmd == "powershell":
        return [
            "powershell",
            "-NoProfile",
            "-Command",
            f'(New-Object Media.SoundPlayer "{file_path}").PlaySync();',
        ]
    if cmd == "ffplay":
        return [cmd, "-nodisp", "-autoexit", "-loglevel", "quiet", file_path]
    return [cmd, file_path]


def _play_with_system_command(file_path: str, blocking: bool) -> bool:
    platform_key = "win32" if sys.platform.startswith("win") else sys.platform
    for base_cmd in _OTHER_CMDS.get(platform_key, []):
        if base_cmd != "powershell" and not shutil.which(base_cmd):
            continue  # command not available
        full_cmd = _build_system_command(base_cmd, file_path)
        if full_cmd is None:
            continue

        try:
            if blocking:
                subprocess.run(full_cmd, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=True)
            else:
                proc = subprocess.Popen(full_cmd, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL,
                                        start_new_session=True)
                _register_playback("system", proc)
            return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------#
# Master helper                                                               #
# ---------------------------------------------------------------------------#
def play_audio(path: str | os.PathLike, *, blocking: bool = True) -> bool:
    """
    Play an audio file through the default Raspberry Pi audio output.

    The function automatically tries Pi-specific back-ends first, followed by
    more generic solutions.  It will raise FileNotFoundError if *path* does
    not exist, otherwise it returns True on success and False on failure.

    Parameters
    ----------
    path : str or PathLike
        File to play.
    blocking : bool, default True
        Wait until playback completes if True.

    Returns
    -------
    bool
        True if playback started, False otherwise.
    """
    file_path = str(Path(path).expanduser().resolve())
    if not Path(file_path).is_file():
        raise FileNotFoundError(f"No such audio file: {file_path}")

    # Strategy order: Pi-preferred → pure python → generic
    strategies: List[Callable[[str, bool], bool]] = []

    if _is_raspberry_pi():
        strategies.extend([
            _play_with_omxplayer,
            _play_with_aplay,
        ])
    strategies.extend([
        _play_with_simpleaudio,
        _play_with_pygame,
        _play_with_playsound,
        _play_with_system_command,
    ])

    for strategy in strategies:
        if strategy(file_path, blocking):
            return True
    return False


# ---------------------------------------------------------------------------#
# Threaded convenience wrapper                                               #
# ---------------------------------------------------------------------------#
class _PlayThread(threading.Thread):
    """
    Background thread that executes `play_audio`.  The boolean return value
    is stored in `self.success` once playback has finished.
    """

    def __init__(self, path: str | os.PathLike, *, blocking: bool = True):
        super().__init__(daemon=True)
        self._path = path
        self._blocking = blocking
        self.success: Optional[bool] = None

    def run(self) -> None:
        try:
            self.success = play_audio(self._path, blocking=self._blocking)
        except Exception:
            # Swallow exceptions so that the thread never terminates with error
            self.success = False


def play(path: str | os.PathLike, *, blocking: bool = True) -> _PlayThread:
    """
    Start audio playback in a dedicated daemon thread and return the thread.

    The call itself is always non-blocking; if you need to wait for
    completion call `thread.join()`.  The boolean result of `play_audio`
    can be inspected afterwards via `thread.success`.

    Parameters
    ----------
    path : str or PathLike
        File to play.
    blocking : bool, default True
        Forwarded to `play_audio` inside the thread.

    Returns
    -------
    _PlayThread
        Thread instance running the playback.
    """
    thread = _PlayThread(path, blocking=blocking)
    thread.start()
    return thread


# Keep stop() convenience alias
stop = stop_audio


# ---------------------------------------------------------------------------#
# Manual test harness                                                         #
# ---------------------------------------------------------------------------#
if __name__ == "__main__":
    # Requirement: simply play “message.wav” in the background and
    # demonstrate stop after 2 s.
    import time

    th = play("message.wav", blocking=True)  # runs in its own thread
    time.sleep(2)
    stop_audio()
    # Wait briefly for the thread to finish up
    th.join(timeout=1)
    sys.exit(0 if (th.success is None or th.success) else 1)
