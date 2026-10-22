text = "the cat and the hat and the bat"
counts = {}
for word in text.split():
    counts[word] = counts.get(word, 0) + 1
for word in sorted(counts):
    print(word, counts[word])
