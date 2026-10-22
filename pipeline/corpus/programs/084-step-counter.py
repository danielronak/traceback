steps = [4200, 8100, 10500, 6000, 12000]
day = 0
total = 0
goal_days = 0
while day < len(steps):
    total += steps[day]
    if steps[day] >= 10000:
        goal_days += 1
    day += 1
print("Total steps:", total)
print(f"Average: {total / len(steps):.0f}")
print("Days over 10000:", goal_days)
