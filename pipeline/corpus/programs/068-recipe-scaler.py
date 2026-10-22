# inputs: 6
recipe = {"flour": 200, "sugar": 100, "eggs": 2}
people = int(input("How many people? "))
scale = people / 4
for ingredient in recipe:
    amount = recipe[ingredient] * scale
    print(f"{ingredient}: {amount:.1f}")
print("Eggs needed:", recipe["eggs"] * scale)
