numbers = [3, 8, 12, 5, 6, 1]
evens = []
for n in numbers:
    if n % 2 == 0:
        evens.append(n)
print("Evens:", evens)
print("Count:", len(evens))
