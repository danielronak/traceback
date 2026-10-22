class Pet:
    def __init__(self, name, sound):
        self.name = name
        self.sound = sound

    def speak(self):
        return self.name + " says " + self.sound


dog = Pet("Rex", "woof")
cat = Pet("Tom", "meow")
print(dog.speak())
print(cat.speak())
