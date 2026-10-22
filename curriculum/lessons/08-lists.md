+++
id = "lists"
title = "Lists: many values in one variable"
teaches = ["index-out-of-range", "zero-division", "none-from-inplace-method", "none-attribute", "off-by-one"]
+++

A **list** holds several values in order, inside square brackets. Like
strings, lists use indexes from 0, and `len()` tells you how many items there
are. Unlike strings, lists can change:

```python
scores = [72, 85, 90]
print(scores[0])
print(len(scores))
scores.append(64)
print(scores)
```

Python has built-in helpers for lists of numbers, such as `sum()`, `max()` and
`min()`:

```python
scores = [72, 85, 90]
print(sum(scores) / len(scores))
print(max(scores))
```

`.sort()` sorts a list *in place*: it changes the list itself and gives back
`None`. `sorted()` gives you a new sorted list and leaves the original alone:

```python
numbers = [3, 1, 2]
print(sorted(numbers))
numbers.sort()
print(numbers)
```

## Common mistakes

The last index is one less than the length:

```python broken=index-out-of-range
letters = ["a", "b", "c"]
print(letters[3])
```

Storing the result of an in-place method:

```python broken=none-from-inplace-method
numbers = [3, 1, 2]
ordered = numbers.sort()
ordered.append(4)
```

Dividing by the length of an empty list:

```python broken=zero-division
scores = []
print(sum(scores) / len(scores))
```
