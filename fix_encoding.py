import os

src_dir = r"D:\Project\Project\GitHelper\src\githelper"
for root, _, files in os.walk(src_dir):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="cp1252") as file:
                content = file.read()
            # replace em-dash with normal dash
            content = content.replace("—", "-")
            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
print("Encoding fixed.")
