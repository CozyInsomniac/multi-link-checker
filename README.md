# Overview
This is a file hosting link checker. It does the following:
1. Check if a list of file hosting links are valid or not.
2. Write the valid link to one file.
3. Write the invalid links to another file.
***
# Installation / Usage (Linux)
**Step 1 - Make / activate a Python virtual environment and instal the required Pip packages.**
```
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
```
***
**Step 2 - Create a `input.txt` file, and paste the URLs in it.**
- The script uses `regex.findall()` to locate URLs, so you shouldn't have to past them in `input.txt` in any special way. 
- You can even include paste site URLs, and the script should parse / extract the file hosting sites from those paste site URLs.
***
**Step 3 - Call the script on input.txt**
```
python3 link_checker.py input.txt
```
- The script should run and finish.
    - Good URLs will be in `/output/good_urls.txt`.
    - Bad URLs will be in `/output/bad_urls.txt` 
***
# Installation / Usage (Windows)
Basically the same thing as linux, but with `\` instead of `/`
***
# To Do
- Add PyInstaller executables for Windows and Linux
- Rewrite the project to be more modular and configurable 
- Impliment `dropbox.com` support
- (Maybe) Add some configuration options
- (Maybe) Make a GUI