words = ["apple", "banana", "kiwi", "cherry"]
longest = words[0]
for word in words:
    if len(word) > len(longest):
        longest = word
print("The longest word is", longest)
print("It has", len(longest), "letters")
