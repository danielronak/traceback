+++
id = "variables"
title = "Giving values a name"
+++
A **variable** is a name for a value, so you can use the value again later.
You create one with `=`:

```python
greeting = "Hello"
print(greeting)
print(greeting)
```

Read `greeting = "Hello"` as "let `greeting` be `"Hello"`". The `=` sign
doesn't mean "is equal to" like in maths; it stores the value on the right
under the name on the left.

## Changing a variable

A variable can be given a new value. From then on, the name means the new
value:

```python
score = 10
print(score)
score = score + 5
print(score)
```

The line `score = score + 5` works out the right-hand side first (`10 + 5`),
then stores the answer back in `score`.

## Choosing names

Names can use letters, digits and underscores, but can't start with a digit.
Python programmers write names in lower case, with underscores between words:
`high_score`, `first_name`. Choose names that say what the value means.

## A common mistake

Python matches names letter for letter. A name spelt slightly differently is
a different name, and Python stops when it meets a name it doesn't know:

```python mistake=name-typo
message = "Hi there"
print(mesage)
```
