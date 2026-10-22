raw_names = ["  ada ", "SAM", " bo", "zoe  "]
clean = []
for name in raw_names:
    clean.append(name.strip().lower())
clean.sort()
print(clean)
for i in range(len(clean)):
    print(i, clean[i].upper())
print("First:", clean[0])
