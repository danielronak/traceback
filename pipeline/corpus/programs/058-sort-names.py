names = ["Zoe", "ada", "Sam", "bo"]
print(sorted(names))
print(sorted(names, key=str.lower))
names.sort(key=len)
print(names)
