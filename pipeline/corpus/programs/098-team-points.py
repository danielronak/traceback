points = {"Reds": 0, "Blues": 0}
results = ["Reds", "Blues", "Reds", "draw", "Reds"]
for winner in results:
    if winner == "draw":
        points["Reds"] += 1
        points["Blues"] += 1
    else:
        points[winner] += 3
print("Reds:", points["Reds"])
print("Blues:", points["Blues"])
print(f"Games played: {len(results)}")
