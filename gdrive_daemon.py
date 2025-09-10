import logging
import subprocess
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

while True:
    log.info("Sync google drive")
    subprocess.Popen("rclone sync recordings/ gdrive:ans_machine_recordings", shell=True)
    time.sleep(60)     