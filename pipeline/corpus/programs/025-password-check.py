# inputs: secret123
password = input("Choose a password: ")
long_enough = len(password) >= 8
has_digit = any(ch.isdigit() for ch in password)
if long_enough and has_digit:
    print("Strong password")
elif long_enough:
    print("Add a number")
else:
    print("Too short")
