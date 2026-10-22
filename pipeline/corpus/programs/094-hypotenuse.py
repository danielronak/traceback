import math


def hypotenuse(a, b):
    result = math.sqrt(a**2 + b**2)
    return result


print("3 and 4:", hypotenuse(3, 4))
print("5 and 12:", hypotenuse(5, 12))
print(f"1 and 1: {hypotenuse(1, 1):.3f}")
