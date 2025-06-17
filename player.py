## @file player.py
## @brief Simple-to-use audio playback helper tailored for the Raspberry Pi.
##
## The implementation uses aplay for .wav audio playback and mpg123 for .mp3 audio playback.
##
## @section helpers Public Helpers
##
## - play_audio(path: str, *, blocking: bool = True) -> bool
##   Start playback of *path* through the default audio device.
##
## - stop_audio() -> bool
##   Best-effort attempt to halt any currently playing audio **and** ensure
##   that any background `_PlayThread` spawned via `play()` terminates.
##
## - play(path: str, *, blocking: bool = True) -> threading.Thread
##   Convenience wrapper that starts a background thread running
##   `play_audio` and returns the Thread instance.
##
## @section usage Typical Usage
##
## @code{.py}
## >>> from player import play, stop
## >>> th = play("/home/pi/sounds/beep.wav")  # fire-and-forget
## >>> # …later…
## >>> stop()        # stop it again
## @endcode

from __future__ import annotations

import os
import sys
import shutil
import threading
import subprocess
from pathlib import Path
from typing import Optional, Callable, Any, List, Tuple

## @brief Internals – keep track of non-blocking playbacks so we can stop them later
_PLAYBACK_HANDLES: List[Tuple[str, Any]] = []   # (backend identifier, handle)
_PLAYBACK_LOCK = threading.Lock()

## @brief Remember a playback handle so that `stop_audio()` can later terminate it.
## Handles are now registered *regardless* of the `blocking` flag so that
## even “blocking” playbacks running in a separate `_PlayThread` can be
## interrupted from the outside.
def _register_playback(backend: str, handle: Any) -> None:
    with _PLAYBACK_LOCK:
        _PLAYBACK_HANDLES.append((backend, handle))

## @brief Helper that returns True if the supplied handle is believed to be
## currently playing.
def _is_handle_active(backend: str, handle: Any) -> bool:
    try:
        if backend in ["aplay", "mpg123"]:
            return handle.poll() is None
    except Exception:
        return False
    return False

## @brief Attempt to stop any audio that is still playing.  This additionally
## causes blocking playbacks that are running inside a background
## `_PlayThread` to return early, so the corresponding thread terminates
## quickly after `stop_audio()` is invoked.
##
## @return bool True if at least one playback was stopped, False otherwise.
def stop_audio() -> bool:
    stopped_any = False
    with _PLAYBACK_LOCK:
        # Work on a copy so we can modify the original list while iterating
        for backend, handle in _PLAYBACK_HANDLES[:]:
            try:
                if not _is_handle_active(backend, handle):
                    _PLAYBACK_HANDLES.remove((backend, handle))
                    continue

                if backend in ["aplay", "mpg123"]:
                    handle.terminate()
                    handle.wait(timeout=1)
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

## @brief This function is the back-end for aplay (ALSA, wav files) and mpg123 (mp3 files). 
## It plays WAV files through ALSA with aplay and MP3 files with mpg123. 
## Suitable for systems where both .wav and .mp3 files are required.
## @param file_path The path of the file to play.
## @param blocking If True, the function will wait until the audio has finished playing.
## @returns True if the audio started playing, False otherwise.
def _play_with_backend(file_path: str, blocking: bool) -> bool:
    file_extension = os.path.splitext(file_path)[1]
    if file_extension == ".wav":
        backend = "aplay"
    elif file_extension == ".mp3":
        backend = "mpg123"
    else:
        return False

    if not shutil.which(backend):
        return False

    cmd = [backend, file_path]  # -q = quiet
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=True)
        _register_playback(backend, proc)
        if blocking:
            proc.wait()
        return True
    except Exception:
        return False

## @brief This is the master helper function. It plays an audio file through the default Raspberry Pi audio output.
## The function uses aplay for .wav audio playback and mpg123 for .mp3 audio playback. 
## It will raise FileNotFoundError if *path* does not exist, 
## otherwise it returns True on success and False on failure.
## @param path The path of the file to play.
## @param blocking If True, the function will wait until the audio has finished playing.
## @returns True if the audio started playing, False otherwise.
def play_audio(path: str | os.PathLike, *, blocking: bool = True) -> bool:
    file_path = str(Path(path).expanduser().resolve())
    if not Path(file_path).is_file():
        raise FileNotFoundError(f"No such audio file: {file_path}")

    return _play_with_backend(file_path, blocking)

## @brief This class is a threaded convenience wrapper. It is a background thread that executes `play_audio`.  
## The boolean return value is stored in `self.success` once playback has finished.
## @param path The path of the file to play.
## @param blocking If True, the function will wait until the audio has finished playing.
## @returns None
class _PlayThread(threading.Thread):
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

## @brief This function starts audio playback in a dedicated daemon thread and returns the thread.
## The call itself is always non-blocking; if you need to wait for completion call `thread.join()`.  
## The boolean result of `play_audio` can be inspected afterwards via `thread.success`.
## @param path The path of the file to play.
## @param blocking If True, the function will wait until the audio has finished playing.
## @returns _PlayThread instance running the playback.
def play(path: str | os.PathLike, *, blocking: bool = True) -> _PlayThread:
    thread = _PlayThread(path, blocking=blocking)
    thread.start()
    return thread

# Keep stop() convenience alias
stop = stop_audio

## @brief This is a manual test harness. It simply plays “message.wav” in the background and demonstrates stop after 2 s.
if __name__ == "__main__":
    import time

    th = play("message_edited.wav", blocking=True)  # runs in its own thread
    time.sleep(2)
    stop_audio()
    # Wait briefly for the thread to finish up
    th.join(timeout=1)
    sys.exit(0 if (th.success is None or th.success) else 1)
