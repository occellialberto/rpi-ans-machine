from keypad import keypad

def on_number_pressed(number):
    if number == 1:
        print("Hai premuto 1: accendo la luce")
        # Aggiungi qui il codice per accendere la luce
    elif number == 2:
        print("Hai premuto 2: spengo la luce")
        # Codice per spegnere la luce
    elif number == 3:
        print("Hai premuto 3: suono il campanello")
        # Codice per suonare campanello
    else:
        print(f"Numero {number} non gestito")

if __name__ == "__main__":
    keypad(callback=on_number_pressed)