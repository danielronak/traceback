word = "mississippi"
seen = set()
for letter in word:
    seen.add(letter)
print(sorted(seen))
print(len(seen), "different letters")
