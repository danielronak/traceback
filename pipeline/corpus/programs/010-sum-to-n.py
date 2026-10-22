# inputs: 10
limit = int(input("Add up to: "))
total = 0
for n in range(1, limit + 1):
    total += n
print("The total is", total)
