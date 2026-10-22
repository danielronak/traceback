text = "the cat sat on the mat and the dog sat too"
words = text.split()
print("Words:", len(words))
print("Times 'the' appears:", words.count("the"))
print("Letter a:", text.count("a"))
longest = ""
for word in words:
    if len(word) > len(longest):
        longest = word
print(f"Longest word: {longest}")
print(text.upper())
