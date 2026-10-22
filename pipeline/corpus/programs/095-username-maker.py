def make_username(first, last, year):
    result = first[:3].lower() + last[:3].lower()
    result += str(year)[-2:]
    return result


print(make_username("Ada", "Lovelace", 1815))
print(make_username("Alan", "Turing", 1912))
print(make_username("Grace", "Hopper", 1906))
