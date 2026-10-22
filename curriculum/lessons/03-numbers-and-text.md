+++
id = "numbers-and-text"
title = "Numbers and text are different things"
teaches = ["input-is-string", "str-plus-int", "int-conversion", "int-conversion-decimal", "input-joined-as-text"]
+++

Every value in Python has a **type**. `7` is a whole number (an `int`), `3.5`
is a decimal (a `float`), and `"7"` is text (a `str`). They can look alike, but
they behave differently. Look at what `+` does with each:

```python
print(7 + 3)
print("7" + "3")
```

With numbers `+` adds; with text it joins. That matters because `input()`
**always gives back text**, even when someone types digits. To do maths with
an answer, convert it with `int()` (or `float()` for decimals):

```python inputs=14
age = int(input("How old are you? "))
print("Next year you will be", age + 1)
```

Going the other way, `str()` turns a number into text, and an **f-string**
puts values into text for you. Put an `f` before the quotes and the values in
curly brackets:

```python
score = 10
print("Your score: " + str(score))
print(f"Your score: {score}")
```

## Common mistakes

Adding a number to the text from `input()`:

```python broken=input-is-string inputs=14
age = input("How old are you? ")
print(age + 1)
```

Joining text and a number with `+`:

```python broken=str-plus-int
score = 10
print("Your score: " + score)
```
