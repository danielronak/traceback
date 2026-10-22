# inputs: 21.5
celsius = float(input("Temperature in C: "))
fahrenheit = celsius * 9 / 5 + 32
print("Fahrenheit:", fahrenheit)
if celsius > 20:
    print("A warm day")
else:
    print("A cool day")
print(f"{celsius} C is {fahrenheit:.1f} F")
