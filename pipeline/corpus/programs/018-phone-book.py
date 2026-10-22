phone_book = {"Ada": "0123", "Sam": "0456"}
phone_book["Bo"] = "0789"
for name in sorted(phone_book):
    print(name, phone_book[name])
print("Zoe" in phone_book)
print(phone_book.get("Zoe", "not found"))
