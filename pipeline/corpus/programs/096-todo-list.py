todo = ["wash up", "homework", "walk dog"]
todo.append("read book")
done = "homework"
todo.remove(done)
print("Done:", done)
print("Left to do:", len(todo))
todo.sort()
for i in range(len(todo)):
    print(f"- {todo[i].capitalize()}")
