timetable = {"Monday": "Maths", "Tuesday": "Art", "Wednesday": "Science"}
timetable["Thursday"] = "History"
print("Monday is", timetable["Monday"])
print("Thursday is", timetable["Thursday"])
days = list(timetable)
days.reverse()
for i in range(len(days)):
    print(i + 1, days[i], timetable[days[i]])
