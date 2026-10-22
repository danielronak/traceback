def describe(n):
    if n < 0:
        return "negative"
    elif n == 0:
        return "zero"
    elif n < 10:
        return "small"
    return "large"


for n in [-3, 0, 7, 42]:
    print(n, describe(n))
