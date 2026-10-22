colours = "red green blue yellow"
words = colours.split()
lengths = {}
for word in words:
    lengths[word] = len(word)
print("green has", lengths["green"], "letters")
print("yellow has", lengths["yellow"], "letters")
words.sort()
print(words)
print(f"Shortest first word: {words[0]}")
