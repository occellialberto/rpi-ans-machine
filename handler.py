class Navigation:
    """Keep menu choices scoped to the current call."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.menu = "PRINCIPALE"

    def handle_number(self, number: str) -> str:
        if self.menu == "PRINCIPALE":
            if number == "10":
                self.menu = "SERVIZI"
                return "MENU_SERVIZI"
            if number == "011351789":
                return "CASA"
            return "NUMERO_NON_VALIDO"

        if number == "1":
            return "ASCOLTA_MESSAGGI"
        if number == "2":
            return "METEO"
        if number == "0":
            self.reset()
            return "MENU_PRINCIPALE"
        return "NUMERO_NON_VALIDO"

def on_number_composed(number, navigation):
    action = navigation.handle_number(str(number))
    print(f"Menu {navigation.menu}: {action}")
    return action

if __name__ == "__main__":
    from keypad import keypad

    navigation = Navigation()
    keypad(lambda number: on_number_composed(number, navigation))
