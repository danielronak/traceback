# inputs: 5 | 10 | 0
total = 0
amount = int(input("Amount (0 to stop): "))
while amount != 0:
    total += amount
    amount = int(input("Amount (0 to stop): "))
print("Total:", total)
