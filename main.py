# @file main.py
# @author Alberto Occelli
# @version 1.0
# @date 09/06/2025
# @brief This script is designed to monitor a GPIO pin, play an audio message, and record audio based on the state of the pin.

import logging
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

from player import play_audio, stop_audio
from keypad import keypad
from handler import on_number_composed

import RPi.GPIO as GPIO

# ---------------------------------------------------------------------------#
# Logging setup                                                              #
# ---------------------------------------------------------------------------#
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------#
# Configuration                                                              #
# ---------------------------------------------------------------------------#
PIN = 17                                   # GPIO pin to monitor (BCM scheme)
MESSAGE_FILE = "messages/message_edited.wav"        # Audio message to be reproduced
RECORD_DIR = Path("recordings/TSOD")            # Directory where recordings land
# Use PulseAudio’s recorder. “--format=cd --file-format=wav” is the closest
# equivalent to the old “arecord -q -f cd -t wav”.
device = "--device=alsa_input.usb-C-Media_Electronics_Inc._USB_Audio_Device-00.mono-fallback"
RECORD_CMD = [
    "parecord",
    "--rate=16000",
    "--channels=1",
    "--format=s16le",
    device,
    "--file-format=wav",
]
POLL_DELAY = 0.01                          # Seconds between GPIO polls
# ---------------------------------------------------------------------------#

## @brief Prepare the GPIO subsystem.
def setup_gpio() -> None:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    log.info("GPIO initialised (BCM pin %s).", PIN)

## @brief Read the monitored pin.
#  @return 0 (LOW) or 1 (HIGH).
def read_gpio() -> int:
    return GPIO.input(PIN)

# ---------------------------------------------------------------------------#
# Playback helper                                                            #
# ---------------------------------------------------------------------------#

## @brief Play MESSAGE_FILE and return a Thread that finishes when playback ends.
#  @param blocking If `blocking=True` the function itself will not return until the audio
#  has been played, but the returned object is still a dummy Thread.
#  @return thread
def _play_message(blocking: bool = False) -> threading.Thread:
    log.info("Starting message playback (%s, blocking=%s).", MESSAGE_FILE, blocking)
    if blocking:
        play_audio(MESSAGE_FILE, blocking=True)
        log.info("Message playback finished (blocking path).")
        return threading.current_thread()  # never queried

    thread = threading.Thread(
        target=play_audio,
        args=(MESSAGE_FILE,),
        kwargs={"blocking": True},  # inside thread: blocking; outside: non-blocking
        daemon=True,
    )
    thread.start()
    return thread

# ---------------------------------------------------------------------------#
# Recording helper                                                           #
# ---------------------------------------------------------------------------#

## @brief Minimal wrapper around a recording subprocess (e.g. `parecord`).
class Recorder:
    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen[str]] = None
        self.file: Optional[Path] = None
        self.start_time: Optional[float] = None

    ## @brief Start recording.
    def start(self) -> None:
        RECORD_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.file = RECORD_DIR / f"call_{timestamp}.wav"
        cmd = [*RECORD_CMD, str(self.file)]
        log.info("Starting recording → %s", self.file)
        self.proc = subprocess.Popen(cmd, start_new_session=True)
        self.start_time = time.time()

    ## @brief Stop recording.
    def stop(self) -> None:
        if self.proc and self.proc.poll() is None and (time.time() - self.start_time) > 1:
            log.info("Stopping recording.")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                log.warning("Recorder did not terminate, killing.")
                self.proc.kill()
            if self.file:
                log.info("Recording saved: %s", self.file)
        self.proc = None
        self.file = None
        self.start_time = None

# ---------------------------------------------------------------------------#
# Main loop                                                                  #
# ---------------------------------------------------------------------------#

## @brief Implements the following state machine:
#  • IDLE: waiting for the handset to be lifted (LOW → HIGH).
#  • PLAY_MESSAGE: play the greeting; the first dial rotation calls
#    callback_rotation and enters DIALING. Without dialing, record as before.
#  • DIALING: wait for the complete number, run callback_number, then return
#    to IDLE. Hanging up (HIGH → LOW) cancels playback/dialing/recording.
#  • RECORDING: record until the handset is hung up.
def main() -> None:
    subprocess.run(["paplay", "o95.wav"])
    setup_gpio()
    last_level = read_gpio()
    state = "IDLE"

    message_thread: Optional[threading.Thread] = None
    recorder = Recorder()
    keypad_events = Queue()
    keypad_stop = threading.Event()
    keypad_thread: Optional[threading.Thread] = None

    def stop_keypad() -> None:
        nonlocal keypad_thread
        keypad_stop.set()
        if keypad_thread is not None:
            keypad_thread.join()
            keypad_thread = None

    def callback_rotation() -> None:
        nonlocal state
        log.info("Dial rotation detected → waiting for number.")
        state = "DIALING"
        stop_audio()

    def callback_number(number: str) -> None:
        nonlocal state
        log.info("Number composed: %s", number)
        try:
            on_number_composed(number)
        except Exception:
            log.exception("Error handling number %s", number)
        finally:
            stop_keypad()
            state = "IDLE"

    try:
        while True:
            level = read_gpio()

            falling_edge = last_level == 1 and level == 0
            rising_edge = last_level == 0 and level == 1

            # ----------------------------- IDLE ----------------------------- #
            if state == "IDLE" and rising_edge:
                time.sleep(0.5)
                log.info("Handset lifted (rising edge) → playing message.")
                keypad_events = Queue()
                keypad_stop.clear()
                keypad_thread = threading.Thread(
                    target=keypad,
                    kwargs={
                        "callback_rotation": lambda: keypad_events.put(("rotation", None)),
                        "callback_number": lambda number: keypad_events.put(("number", number)),
                        "multiple": True,
                        "stop_event": keypad_stop,
                    },
                    daemon=True,
                )
                keypad_thread.start()
                message_thread = _play_message(blocking=False)
                state = "PLAY_MESSAGE"

            # Callbacks run here, so only the main thread changes state.
            if state in ("PLAY_MESSAGE", "DIALING") and falling_edge:
                log.info("Handset hung up → aborting.")
                stop_audio()
                stop_keypad()
                state = "IDLE"

            while True:
                try:
                    event, number = keypad_events.get_nowait()
                except Empty:
                    break
                if event == "rotation" and state == "PLAY_MESSAGE":
                    callback_rotation()
                elif event == "number" and state == "DIALING":
                    callback_number(number)

            # ------------------------ PLAY_MESSAGE ------------------------- #
            if state == "PLAY_MESSAGE":
                if message_thread and not message_thread.is_alive():
                    log.info("Message playback finished → starting recording.")
                    stop_keypad()
                    recorder.start()
                    state = "RECORDING"

            # -------------------------- RECORDING -------------------------- #
            elif state == "RECORDING" and falling_edge:
                log.info("Hang down detected.")
                recorder.stop()
                state = "IDLE"

            last_level = level
            time.sleep(POLL_DELAY)

    except KeyboardInterrupt:
        log.info("Keyboard interrupt received – exiting.")

    finally:
        stop_keypad()
        stop_audio()
        recorder.stop()
        GPIO.cleanup()
        log.info("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
