# inputs: 15
goal = 100
saved = 0
weeks = 0
weekly = int(input("Save per week: "))
while saved < goal:
    saved += weekly
    weeks += 1
print("Weeks needed:", weeks)
print(f"Saved: {saved}")
