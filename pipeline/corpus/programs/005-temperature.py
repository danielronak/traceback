# inputs: 21
celsius = float(input("Temperature in Celsius: "))
fahrenheit = celsius * 9 / 5 + 32
print(f"{celsius} C is {fahrenheit} F")
if fahrenheit > 70:
    print("That's warm.")
else:
    print("That's cool.")
