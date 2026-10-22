# inputs: 48 | 15
bill = float(input("Bill amount: "))
percent = int(input("Tip percent: "))
tip = bill * percent / 100
print(f"Tip: {tip:.2f}")
print(f"Total: {bill + tip:.2f}")
