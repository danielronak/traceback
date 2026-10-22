# inputs: Ada Lovelace
full_name = input("Your full name: ")
parts = full_name.split()
initials = ""
for part in parts:
    initials += part[0].upper()
print("Your initials are", initials)
