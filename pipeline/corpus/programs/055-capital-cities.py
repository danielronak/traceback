capitals = {"France": "Paris", "Japan": "Tokyo", "Kenya": "Nairobi"}
for country in capitals:
    print(f"The capital of {country} is {capitals[country]}")
capitals["Peru"] = "Lima"
print(len(capitals), "countries")
