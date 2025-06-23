import RPi.GPIO as GPIO
import time

# Usa la numerazione BCM (i numeri GPIO, non i pin fisici)
GPIO.setmode(GPIO.BCM)

# Pin da monitorare
PINS = [10, 11]

# Configura i pin come input con pull-up (modifica se serve pull-down)
for pin in PINS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

print(f"Monitoraggio stato GPIO {PINS[0]} e {PINS[1]} (premi Ctrl+C per uscire)")

try:
    while True:
        states = {pin: GPIO.input(pin) for pin in PINS}
        print(f"GPIO {PINS[0]}: {'ALTO' if states[PINS[0]] else 'BASSO'} | GPIO {PINS[1]}: {'ALTO' if states[PINS[1]] else 'BASSO'}", end='\r')
        time.sleep(0.01)

except KeyboardInterrupt:
    print("\nUscita dal monitor.")
finally:
    GPIO.cleanup()
