class UserSettings:
    def __init__(self, user_id):
        self.user_id = user_id
        self.visible = True
        self.dark_mode = False

    def go_ghost(self):
        self.visible = False

    def activate_dark_mode(self):
        self.dark_mode = True

    def deactivate_dark_mode(self):
        self.dark_mode = False

    def display_settings_summary(self):
        visibility = "👻 Unsichtbar" if not self.visible else "🧍 Sichtbar"
        dark = "🌙 Dark Mode aktiviert" if self.dark_mode else "☀️ Dark Mode deaktiviert"
        return f"{visibility}\n{dark}"
