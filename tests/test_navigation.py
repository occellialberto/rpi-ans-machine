import unittest

from handler import Navigation


class NavigationTests(unittest.TestCase):
    def test_services_require_entry_number(self):
        navigation = Navigation()
        for number in ("1", "2"):
            self.assertEqual(navigation.handle_number(number), "NUMERO_NON_VALIDO")
        self.assertEqual(navigation.handle_number("10"), "MENU_SERVIZI")
        self.assertEqual(navigation.handle_number("1"), "ASCOLTA_MESSAGGI")
        self.assertEqual(navigation.handle_number("2"), "METEO")

    def test_back_disables_service_choices(self):
        navigation = Navigation()
        navigation.handle_number("10")
        self.assertEqual(navigation.handle_number("0"), "MENU_PRINCIPALE")
        self.assertEqual(navigation.handle_number("1"), "NUMERO_NON_VALIDO")

    def test_reset_disables_services_for_next_call(self):
        navigation = Navigation()
        navigation.handle_number("10")
        navigation.reset()
        self.assertEqual(navigation.handle_number("2"), "NUMERO_NON_VALIDO")

    def test_invalid_choice_preserves_current_menu(self):
        navigation = Navigation()
        navigation.handle_number("10")
        self.assertEqual(navigation.handle_number("99"), "NUMERO_NON_VALIDO")
        self.assertEqual(navigation.handle_number("2"), "METEO")

    def test_existing_home_number(self):
        self.assertEqual(Navigation().handle_number("011351789"), "CASA")


if __name__ == "__main__":
    unittest.main()
