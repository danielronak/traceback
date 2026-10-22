menu = {"tea": 1.50, "coffee": 2.20, "cake": 3.00}
order = ["tea", "cake", "tea"]
total = 0
for item in order:
    total += menu[item]
print(f"Order total: {total:.2f}")
