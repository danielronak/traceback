def biggest(numbers):
    best = numbers[0]
    for n in numbers:
        if n > best:
            best = n
    return best


print(biggest([3, 9, 2, 7]))
print(biggest([-5, -1, -8]))
