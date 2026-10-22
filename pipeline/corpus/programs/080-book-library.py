class Book:
    def __init__(self, title, pages):
        self.title = title
        self.pages = pages
        self.read = 0

    def read_pages(self, count):
        self.read += count
        if self.read > self.pages:
            self.read = self.pages

    def progress(self):
        return f"{self.title}: {self.read} of {self.pages} pages"


book = Book("Python Basics", 120)
book.read_pages(50)
print(book.progress())
book.read_pages(90)
print(book.progress())
