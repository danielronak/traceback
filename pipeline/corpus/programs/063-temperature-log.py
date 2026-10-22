temps = [12.5, 14.0, 9.5, 16.0, 11.0]
count = 0
warm_days = 0
while count < len(temps):
    if temps[count] > 12:
        warm_days += 1
    count += 1
temps.sort()
print("Coldest:", temps[0])
print("Warmest:", temps[-1])
print(f"Warm days: {warm_days}")
