# inputs: 3725
seconds = int(input("Seconds: "))
hours = seconds // 3600
minutes = seconds % 3600 // 60
remaining = seconds % 60
print(f"{hours}h {minutes}m {remaining}s")
