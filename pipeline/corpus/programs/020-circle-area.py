import math


def circle_area(radius):
    return math.pi * radius ** 2


for radius in [1, 2.5, 10]:
    area = circle_area(radius)
    print(f"Radius {radius}: area {area:.2f}")
