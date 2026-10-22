grid = [[1, 2, 3], [4, 5, 6]]
for row in grid:
    print(row)
print("Top right:", grid[0][2])
total = 0
for row in grid:
    total += sum(row)
print("Sum:", total)
