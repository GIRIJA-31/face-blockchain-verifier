"""
Isolated test: can Selenium + Edge attach a local file to a plain
<input type="file"> at all on this machine? This has nothing to do with
Google - it's a sanity check to rule in/out a local driver/browser
mismatch before debugging Google's page any further.

Usage:
    python test_file_upload.py
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By

try:
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    AUTO_DRIVER = True
except ImportError:
    AUTO_DRIVER = False


# 1. Build a tiny local HTML page with a plain file input
html_path = os.path.abspath("test_upload_page.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write("""
    <html><body>
        <h3>Plain file input test</h3>
        <input type="file" id="fileInput">
        <div id="result">no file yet</div>
        <script>
            document.getElementById('fileInput').addEventListener('change', function(e) {
                document.getElementById('result').innerText =
                    e.target.files.length ? e.target.files[0].name : 'still empty';
            });
        </script>
    </body></html>
    """)

# 2. Pick a real file to try uploading - reuse whatever's in data/ if present
candidate = None
if os.path.isdir("data"):
    for fname in os.listdir("data"):
        if fname.lower().endswith((".jpg", ".jpeg", ".png")):
            candidate = os.path.abspath(os.path.join("data", fname))
            break
if candidate is None:
    # fall back to making a trivial dummy file
    candidate = os.path.abspath("dummy_test_file.txt")
    with open(candidate, "w") as f:
        f.write("test")

print(f"Testing upload of: {candidate}")

# 3. Same driver setup as the main script
options = EdgeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

if AUTO_DRIVER:
    service = EdgeService(EdgeChromiumDriverManager().install())
    driver = webdriver.Edge(service=service, options=options)
else:
    driver = webdriver.Edge(options=options)

try:
    driver.get(f"file:///{html_path}")
    time.sleep(1)

    file_input = driver.find_element(By.ID, "fileInput")
    file_input.send_keys(candidate)
    time.sleep(1)

    files_info = driver.execute_script(
        "return arguments[0].files.length ? arguments[0].files[0].name : 'EMPTY';",
        file_input,
    )
    result_text = driver.find_element(By.ID, "result").text

    print(f"input.files[0].name -> {files_info}")
    print(f"page's own change-event handler saw -> {result_text}")

    if files_info != "EMPTY":
        print("\nSUCCESS: Selenium CAN attach files on this machine.")
        print("This means the problem is specific to Google's page, not your environment.")
    else:
        print("\nFAILURE: Selenium could NOT attach a file even on a plain local page.")
        print("This points to a local driver/Edge version mismatch. Try:")
        print("  1. Check your Edge version at edge://version")
        print("  2. Delete the folder C:\\Users\\<you>\\.wdm to clear the cached driver")
        print("  3. Re-run this test - webdriver-manager will download a fresh matching driver")

finally:
    input("\nPress Enter to close...")
    driver.quit()