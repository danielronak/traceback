class Lamp:
    def __init__(self, room):
        self.room = room
        self.is_on = False

    def toggle(self):
        self.is_on = not self.is_on
        if self.is_on:
            return self.room + " lamp is on"
        return self.room + " lamp is off"


presses = 0
lamp = Lamp("Kitchen")
while presses < 3:
    print(lamp.toggle())
    presses += 1
print("Presses:", presses)
