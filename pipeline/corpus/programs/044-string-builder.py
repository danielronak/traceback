words = ["Python", "is", "fun"]
sentence = ""
for word in words:
    sentence = sentence + word + " "
print(sentence.strip())
print(str(len(words)) + " words")
