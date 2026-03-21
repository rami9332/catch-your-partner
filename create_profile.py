import os
import subprocess
from user_profile import UserProfile

def main():
    print("👤 Neues Nutzerprofil erstellen")
    name = input("Name: ")
    age = int(input("Alter: "))
    interests = input("Interessen (durch Komma getrennt): ").split(",")
    looking_for = input("Wonach suchst du? (Beziehung, Spaß, Freundschaft...): ")

    # Bildpfad vorbereiten
    image_path = f"uploads/{name}.jpg"

    # Bild existiert?
    if not os.path.exists(image_path):
        print(f"❌ Profilbild '{image_path}' nicht gefunden.")
        return

    # Gesichtsanalyse starten
    result = subprocess.run(["python3", "check_image.py", image_path], capture_output=True, text=True)

    if "❌" in result.stdout:
        print(result.stdout)
        print("❌ Profilbild wurde abgelehnt.")
        os.rename(image_path, f"rejected/{name}.jpg")
        return
    else:
        print(result.stdout)

    # Profil anlegen
    user = UserProfile(name, age, interests, looking_for)

    with open("user_data.txt", "a") as file:
        file.write(f"{user.name},{user.age},{','.join(user.interests)},{user.looking_for}\n")

    print("✅ Profil erfolgreich erstellt.")

if __name__ == "__main__":
    main()
