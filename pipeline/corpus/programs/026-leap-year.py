def is_leap(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0


for year in [1900, 2000, 2024, 2023]:
    print(year, is_leap(year))
