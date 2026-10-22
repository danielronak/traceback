# inputs: 48.00 | 3
bill = float(input("Bill: "))
people = int(input("People: "))
tip = bill * 0.1
total = bill + tip
share = total / people
print("Tip:", tip)
print(f"Total: {total:.2f}")
print(f"Each pays: {share:.2f}")
