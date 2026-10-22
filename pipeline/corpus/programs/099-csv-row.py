row = "Ada,36,London"
parts = row.split(",")
name = parts[0]
age = int(parts[1])
city = parts[2].upper()
print("Name:", name)
print("Next year:", age + 1)
print(f"City: {city}")
print(row.replace(",", " | "))
