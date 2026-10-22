# inputs: twelve | 12
while True:
    text = input("Enter a number: ")
    try:
        number = int(text)
        break
    except ValueError:
        print("That's not a whole number.")
print("Double is", number * 2)
