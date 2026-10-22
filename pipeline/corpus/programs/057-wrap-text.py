text = "Python is a friendly language to learn"
width = 12
line = ""
for word in text.split():
    if len(line) + len(word) + 1 > width:
        print(line)
        line = word
    else:
        line = (line + " " + word).strip()
print(line)
