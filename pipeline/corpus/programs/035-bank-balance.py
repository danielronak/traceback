balance = 100
deposits = [20, 35]
withdrawals = [50, 10]
for amount in deposits:
    balance += amount
for amount in withdrawals:
    balance -= amount
print("Final balance:", balance)
if balance < 0:
    print("Overdrawn!")
