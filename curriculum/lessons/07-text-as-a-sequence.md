+++
id = "text-as-a-sequence"
title = "Text is a sequence of letters"
teaches = ["str-immutable", "attribute-typo", "attribute-missing", "index-out-of-range"]
+++

A string is a sequence of characters, and you can pick them out by position.
Positions (called **indexes**) start at 0, and negative ones count from the
end:

```python
word = "Python"
print(word[0])
print(word[-1])
print(len(word))
```

A `for` loop goes through a string one character at a time:

```python
for letter in "hey":
    print(letter)
```

A **slice** takes part of a string: `word[start:stop]`, stopping just before
`stop`. A third number is a step, so `[::-1]` walks backwards. Strings also
have **methods**, functions that belong to them, called with a dot:

```python
word = "stressed"
print(word[0:3])
print(word[::-1])
print(word.upper())
print("Hello" in "Hello, world")
```

## Common mistakes

Strings can't be changed in place. Make a new one instead:

```python broken=str-immutable
word = "cat"
word[0] = "b"
```

Method names must be spelled exactly:

```python broken=attribute-typo
word = "hello"
print(word.uper())
```
