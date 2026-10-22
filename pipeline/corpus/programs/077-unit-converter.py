def convert(value, rate, unit):
    result = value * rate
    return f"{result:.2f} {unit}"


print(convert(5, 1.609, "km"))
print(convert(10, 2.54, "cm"))
print(convert(3, 0.454, "kg"))
