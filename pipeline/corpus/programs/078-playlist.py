playlist = ["Song A", "Song B", "Song C"]
playlist.append("Song D")
playlist.remove("Song B")
playlist.reverse()
print("Tracks:", len(playlist))
for i in range(len(playlist)):
    print(f"{i + 1}. {playlist[i]}")
print("Last played:", playlist[-1])
