def average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


scores = [72, 85, 90, 64]
print("Average:", average(scores))
print("Empty:", average([]))
