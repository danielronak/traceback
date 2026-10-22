totals = {}
for first in range(1, 7):
    for second in range(1, 7):
        score = first + second
        totals[score] = totals.get(score, 0) + 1
print("Ways to roll 7:", totals[7])
print("Ways to roll 12:", totals[12])
