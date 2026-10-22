size = 4
for row in range(1, size + 1):
    line = ""
    for col in range(1, size + 1):
        line += str(row * col).rjust(4)
    print(line)
