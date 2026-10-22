+++
id = "printing"
title = "Showing things on the screen"
+++
A program is a list of instructions that the computer follows, one line at a
time, from the top down. The first instruction most people learn is `print`,
which shows something on the screen.

```python
print("Hello!")
print("I am learning Python.")
```

Press **Run** and the two messages appear, in order.

## Text goes in quote marks

A piece of text in a program is called a **string**. You write a string
inside quote marks, so Python knows where the text starts and stops. Double
quotes `"like this"` and single quotes `'like this'` both work, as long as
the two ends match.

Numbers don't need quote marks. Python can also work out sums for you:

```python
print(7)
print(2 + 3)
print("2 + 3")
```

The second line prints `5`, because Python worked out the sum. The third
prints `2 + 3`, because it's a string, and Python shows strings exactly as
they are written.

## A common mistake

If a string has no closing quote mark, Python can't tell where the text ends,
so it can't run the program at all. Try running this and read the card that
explains it:

```python mistake=unterminated-string
print("Hello!)
```
