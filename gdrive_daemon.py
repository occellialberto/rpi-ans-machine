import logging
import subprocess
import time

log = logging.getLogger(__name__)

while True:
    log.info("Sync google drive")
    subprocess.Popen("rclone sync recordings/ gdrive:ans_machine_recordings", shell=True)
    time.sleep(60)     