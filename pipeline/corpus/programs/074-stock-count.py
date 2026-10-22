stock = {"apples": 10, "pears": 4, "plums": 0}
stock["apples"] -= 3
stock["pears"] += 6
print("Apples:", stock["apples"])
print("Pears:", stock["pears"])
empty = []
for fruit in stock:
    if stock[fruit] == 0:
        empty.append(fruit)
print("Sold out:", empty)
