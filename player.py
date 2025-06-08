"""
player.py

Simple-to-use audio playback helper tailored for the Raspberry Pi.
The implementation tries several different playback back-ends, choosing
those that are most likely to be present on a Pi first (omxplayer, aplay),
but it will gracefully fall back to pure-python solutions if available.

Public function
---------------
play_audio(path: str, *, blocking: bool = True) -> bool
    Play *path* through the default audio device.  The function returns
    True when playback could be started, False otherwise.

Typical usage
-------------
>>> from player import play_audio
>>> play_audio("/home/pi/sounds/beep.wav")            # wait until finished
>>> play_audio("/home/pi/sounds/alert.mp3", blocking=False)

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
from typing import Optional, Callable


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
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
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
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
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


def _build_system_command(cmd: str, file_path: str) -> Optional[list[str]]:
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
                subprocess.Popen(full_cmd, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 start_new_session=True)
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
    strategies: list[Callable[[str, bool], bool]] = []

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


# Allow shorter alias
play = play_audio


# ---------------------------------------------------------------------------#
# Manual test harness                                                         #
# ---------------------------------------------------------------------------#
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Play an audio file.")
    parser.add_argument("file", help="Audio file to play")
    parser.add_argument("-n", "--non-blocking", action="store_true",
                        help="Return immediately (non-blocking mode)")
    args = parser.parse_args()

    success = play_audio(args.file, blocking=not args.non_blocking)
    sys.exit(0 if success else 1)

