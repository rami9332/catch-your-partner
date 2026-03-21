class UserProfile:
    def __init__(self, first_name, birth_date, gender, looking_for, country, native_language, search_purpose, interests, profile_picture_url):
        self.first_name = first_name
        self.birth_date = birth_date
        self.gender = gender
        self.looking_for = looking_for
        self.country = country
        self.native_language = native_language
        self.search_purpose = search_purpose
        self.interests = interests
        self.profile_picture_url = profile_picture_url
        self.user_id = first_name.lower() + "_" + birth_date.replace("-", "")

    def display_profile_summary(self):
        return f"""
👤 Name: {self.first_name}
🎂 Geburtstag: {self.birth_date}
🔍 Sucht: {', '.join(self.looking_for)}
🌍 Land: {self.country}
"""

# Beispielhafte Verwendung – kann bei Bedarf in andere Datei ausgelagert werden
if __name__ == "__main__":
    user1 = UserProfile(
        first_name="Ali",
        birth_date="1995-06-15",
        gender="Male",
        looking_for=["Female"],
        country="Egypt",
        native_language="Arabic",
        search_purpose=["Relationship", "Friendship"],
        interests=["Football", "Travel", "Cooking"],
        profile_picture_url="path/to/profile1.jpg"
    )

    print(user1.display_profile_summary())
