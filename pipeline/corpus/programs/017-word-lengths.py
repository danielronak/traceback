words = ["sun", "moon", "stars"]
lengths = {}
for word in words:
    lengths[word] = len(word)
print(lengths)
for word, size in lengths.items():
    print(word, "has", size, "letters")
