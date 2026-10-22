def count_vowels(text):
    count = 0
    for letter in text.lower():
        if letter in "aeiou":
            count += 1
    return count


word = "Programming"
print(word, "has", count_vowels(word), "vowels")
