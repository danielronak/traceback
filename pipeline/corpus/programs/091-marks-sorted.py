marks = [64, 81, 47, 90, 73]
marks.append(58)
marks.sort()
print("Lowest:", marks[0])
print("Highest:", marks[-1])
marks.reverse()
for i in range(3):
    print(f"Place {i + 1}: {marks[i]}")
