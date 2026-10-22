# inputs: 2.5
import math

radius = float(input("Radius: "))
area = math.pi * radius**2
circumference = 2 * math.pi * radius
print(f"Area: {area:.2f}")
print(f"Circumference: {circumference:.2f}")
print("Rounded area:", round(area))
