# @file main.py
# @author Alberto Occelli
# @version 1.0
# @date 09/06/2025
# @brief This script is designed to monitor a GPIO pin and play an audio message.

import logging
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from player import play_audio, stop_audio

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
MESSAGE_FILE = "message_edited.wav"        # Audio message to be reproduced
POLL_DELAY = 0.02                          # Seconds between GPIO polls
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
# Main loop                                                                  #
# ---------------------------------------------------------------------------#

## @brief Implements the following state machine:
#  • IDLE: waiting for GPIO to go from HIGH (1) to LOW (0).
#  • PLAY_MESSAGE: reproducing MESSAGE_FILE. If GPIO returns HIGH before
#  playback completes → abort and return to IDLE.
def main() -> None:
    subprocess.run(["paplay", "o95.wav"])
    setup_gpio()
    last_level = read_gpio()
    state = "IDLE"

    message_thread: Optional[threading.Thread] = None

    try:
        while True:
            level = read_gpio()

            falling_edge = last_level == 1 and level == 0
            rising_edge = last_level == 0 and level == 1

            # ----------------------------- IDLE ----------------------------- #
            if state == "IDLE" and rising_edge:
                time.sleep(0.5)
                log.info("Hang down detected (rising edge) → playing message.")
                message_thread = _play_message(blocking=False)
                state = "PLAY_MESSAGE"

            # ------------------------ PLAY_MESSAGE ------------------------- #
            elif state == "PLAY_MESSAGE":
                # Abort if pin goes high before message ends
                if falling_edge:
                    log.info("Hang up detected during playback → aborting.")
                    stop_audio()
                    state = "IDLE"

            last_level = level
            time.sleep(POLL_DELAY)

    except KeyboardInterrupt:
        log.info("Keyboard interrupt received – exiting.")

    finally:
        stop_audio()
        GPIO.cleanup()
        log.info("GPIO cleaned up. Bye!")


if __name__ == "__main__":
    main()
