def weekly_total(base, chores, rate):
    result = base
    result += chores * rate
    return result


print("Ada:", weekly_total(5, 3, 0.5))
print("Sam:", weekly_total(5, 0, 0.5))
print("Bo:", weekly_total(4, 6, 0.75))
