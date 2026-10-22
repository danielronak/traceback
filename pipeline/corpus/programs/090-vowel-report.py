# inputs: Banana Bread
phrase = input("Type a phrase: ").lower()
vowels = 0
for letter in phrase:
    if letter in "aeiou":
        vowels += 1
print("Vowels:", vowels)
print("Letter a:", phrase.count("a"))
print(f"Shouting: {phrase.upper()}")
