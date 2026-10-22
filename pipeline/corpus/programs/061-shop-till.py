prices = {"tea": 1.5, "milk": 0.9, "bread": 1.2, "jam": 2.5}
basket = ["tea", "bread", "jam"]
basket.append("milk")
total = 0
for item in basket:
    total += prices[item]
print("Items:", len(basket))
print(f"Total: {total:.2f}")
print("Tea costs", prices["tea"])
if total > 5:
    print("You get a free bag.")
