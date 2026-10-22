# inputs: 2 | 3
prices = {"adult": 9.0, "child": 5.5}
adults = int(input("Adults: "))
children = int(input("Children: "))
cost = adults * prices["adult"] + children * prices["child"]
if adults + children >= 5:
    cost -= 4
print("Tickets:", adults + children)
print(f"Cost: {cost:.2f}")
