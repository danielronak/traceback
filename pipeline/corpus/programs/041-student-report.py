students = {"Ada": [90, 85], "Sam": [70, 65], "Bo": [88, 92]}
for name, marks in students.items():
    average = sum(marks) / len(marks)
    if average >= 80:
        result = "merit"
    else:
        result = "pass"
    print(f"{name}: {average} ({result})")
