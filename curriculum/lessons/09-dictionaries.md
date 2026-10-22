+++
id = "dictionaries"
title = "Dictionaries: looking things up by name"
teaches = ["key-missing"]
+++

A **dictionary** stores pairs: a **key** and its **value**, like a word and its
meaning. You look values up by key instead of by position:

```python
ages = {"Ada": 36, "Sam": 12}
print(ages["Ada"])
ages["Bo"] = 7
print(ages)
```

Assigning to a key adds it, or replaces its value if it's already there. A
`for` loop over a dictionary goes through its keys:

```python
ages = {"Ada": 36, "Sam": 12}
for name in ages:
    print(name, "is", ages[name])
```

To look up a key that might be missing, use `.get()` with a default, or check
first with `in`:

```python
ages = {"Ada": 36}
print(ages.get("Zoe", "unknown"))
print("Zoe" in ages)
```

## Common mistakes

Looking up a key that isn't there:

```python broken=key-missing
ages = {"Ada": 36}
print(ages["Zoe"])
```
