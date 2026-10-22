+++
id = "printing"
title = "Showing things on screen"
teaches = ["print-statement", "unterminated-string", "name-meant-string", "missing-comma"]
+++

A program talks to you through `print()`. Whatever you put inside the round
brackets appears on the screen, one line per `print()`. Press **Run** to try it.

```python
print("Hello, world!")
print("I am learning Python.")
```

Text in Python is called a **string**, and it always goes inside quote marks.
You can use `"double"` or `'single'` quotes, as long as both ends match.
Numbers don't need quotes, and Python works them out first:

```python
print(7)
print(2 + 2)
```

To print several things on one line, separate them with commas. Python puts a
space between them for you.

```python
print("Two plus two is", 2 + 2)
```

## Common mistakes

Forget the quotes, and Python thinks your words are the name of a variable:

```python broken=name-meant-string
print(hello)
```

Forget the closing quote, and Python can't tell where your text ends:

```python broken=unterminated-string
print("Hello)
```

Press **Run** on either one to see how PyMentor explains it.
