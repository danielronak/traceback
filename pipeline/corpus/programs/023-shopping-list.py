shopping = []
shopping.append("milk")
shopping.append("bread")
shopping.append("eggs")
shopping.remove("bread")
print("Shopping list:")
for item in shopping:
    print("-", item)
print(len(shopping), "items")
