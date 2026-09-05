# face-blockchain-verifier

A pipeline that takes a face image, performs a **genuine reverse image search**
to find a real matching post about that person on the web/social media, and
records a **tamper-evident fingerprint** of the discovery on a local Ethereum
blockchain (Ganache) — with re-verification of the stored record against a
freshly recomputed hash.

Built for **HH Goa 2026 Shortlisting — Task #3: Face Identification & Blockchain Verification**.

---

## Pipeline overview

```
Face image (data/)
        |
        v
Face detection + encoding  ───────────  InsightFace (buffalo_l model)
        |
        v
Reverse image search       ───────────  Selenium + Microsoft Edge + Google Lens
   -> finds a real matching post/source (genuine search, not hardcoded)
        |
        v
SHA-256 fingerprint of (image bytes + match data + face embedding)
        |
        v
Stored as a blockchain transaction  ──  Ganache (local Ethereum) via web3.py
        |
        v
Re-verification: the record is read back from the chain and checked
against a freshly recomputed fingerprint  ──  MATCH / MISMATCH
```

---

## Project structure

```
face-blockchain-verifier/
├── data/                      # input images go here (e.g. data/sam.jpg)
├── src/
│   ├── register.py            # enrolls a face (saves an embedding to data/)
│   ├── verify.py               # face-vs-face verification + writes result to blockchain
│   ├── web_search.py           # Google Lens reverse image search automation
│   ├── pipeline.py             # ⭐ full end-to-end pipeline (the main deliverable)
│   ├── blockchain.py           # reads and prints every record stored on the chain
│   └── main.py                 # menu to run any of the above
├── .gitignore
└── README.md
```

---

## What you need to install before setup

### 1. Python 3.10+
Download from [python.org](https://www.python.org/downloads/) if you don't have it. Confirm with:
```bash
python --version
```

### 2. Microsoft Edge
Any recent version — required for the reverse image search step. Most Windows machines already have it; if not, download from [microsoft.com/edge](https://www.microsoft.com/edge).

### 3. Ganache (local Ethereum blockchain)
Download the desktop app from [trufflesuite.com/ganache](https://trufflesuite.com/ganache/) and install it.

- Open Ganache and click **"Quickstart"** to spin up a local test blockchain.
- Confirm the **RPC Server** address shown at the top matches `HTTP://127.0.0.1:7545` (this project's scripts are hardcoded to this URL). If Ganache shows a different port, either change it in Ganache's settings to `7545`, or update `GANACHE_URL` in `src/pipeline.py`, `src/verify.py`, and `src/blockchain.py` to match.
- **Leave Ganache running** in the background the entire time you use this project — every blockchain-related script connects to it live.

### 4. Git
Needed to clone/push the repo. Download from [git-scm.com](https://git-scm.com/downloads) if you don't have it.

---

## Python dependencies

From the project root, with your virtual environment activated:

```bash
python -m venv venv
venv\Scripts\activate          # on Windows
pip install selenium webdriver-manager pyautogui opencv-python numpy insightface web3
```

> **Note:** the first time you run any face-related script, InsightFace will automatically download its model files (~a few hundred MB) to `~/.insightface/models/` — this requires an internet connection on first run only.

---

## Setup checklist before running anything

- [ ] Ganache is open and running (Quickstart mode)
- [ ] Virtual environment is activated (`venv\Scripts\activate`)
- [ ] Dependencies installed (see above)
- [ ] At least one image is placed in the `data/` folder, containing exactly one clearly visible face (e.g. `data/sam.jpg`)

---

## How to run

From the project root:

```bash
python src\main.py
```

You'll see a menu:

```
1. Register Face
2. Verify Face
3. View Blockchain Records
4. Full Pipeline (Face -> Web Search -> Blockchain)
5. Exit
```

- **Option 1** — registers a face (saves its embedding) for later comparison. Optional, not required for the core task.
- **Option 2** — compares a new image against the registered face and writes the verification result to the blockchain.
- **Option 3** — prints every transaction currently stored on your local Ganache chain, decoding any readable data.
- **Option 4 — the main deliverable.** Runs the entire pipeline in one go: face scan → web search → blockchain record → re-verification.
- **Option 5** — exits.

For the full pipeline, you'll be prompted:
```
Enter image name (in data/ folder): sam.jpg
```
Type the exact filename (including extension) of an image already sitting in `data/`.

### What happens when you run the full pipeline

1. **Face detection + encoding** — InsightFace detects the face and produces a 512-dimensional embedding. If multiple faces are detected, the largest face in the frame is treated as the main subject.
2. **Reverse image search** — a real, visible Microsoft Edge window opens (controlled by Selenium), navigates to Google Lens, and uploads your image through the actual "upload a file" dialog (driven via `pyautogui` — see *Design notes* below for why).
3. **Match extraction** — the script reads Google Lens's results and extracts a genuine matching source (name + content), preferring known social platforms when present.
4. **Fingerprinting** — a SHA-256 hash is computed over the image bytes, the discovered match data, and the face embedding together.
5. **Blockchain write** — the fingerprint and match metadata are encoded into a transaction sent to your local Ganache chain.
6. **Re-verification** — the transaction is read back from the chain, and its stored data is checked against a freshly recomputed hash, printing **MATCH** or **MISMATCH**.

---

## Which blockchain, and why

A **local Ethereum test network via Ganache**, accessed through **web3.py**. Each discovery is stored as a zero-value transaction sent from a Ganache account to itself, with the record encoded in the transaction's `data` field. This satisfies the task's explicit allowance for a "local/simulated chain," avoids any real gas cost or network dependency, and makes every record independently re-verifiable by re-reading the transaction and recomputing the hash — exactly what the task asks for ("demonstrate re-verifying the data against the on-chain record").

---

## Design notes: why the web search step works the way it does

Standard Selenium file-upload (`send_keys()` on the hidden `<input type="file">`) does **not** work against Google Lens — this was confirmed directly during development: `input.files` remained empty after `send_keys()`, with no error raised, even though the identical technique worked correctly on a plain local test page. Google's page appears to reject non-native file attachment specifically.

The working solution instead clicks the real **"upload a file"** link, which opens the actual native Windows file picker, and uses `pyautogui` to type the file path into that real OS dialog and press Enter — the same physical action a person takes manually. This is not a generic Selenium workaround; it's specifically necessary for Google Lens.

Additionally, Google Lens's result cards are rendered as JavaScript-driven elements rather than standard `<a href>` anchor tags, so the script extracts the visible **source name + headline text** of each result directly, rather than relying on a clickable URL.

---

## Known limitations

- **No clickable source URL.** Because Google Lens's result cards are JS-driven rather than anchor links, the discovered "matching post" is captured as text/metadata (source name + headline), not a direct URL. This is explicitly permitted by the task ("upload the post... e.g. the image, text, or metadata").
- **Match relevance varies by image.** The search step is genuine and non-hardcoded, but Google Lens ranks by visual similarity, not confirmed identity — for some images the top result is clearly about the person, while for others it may be a visually-similar but less directly relevant post. This reflects Google Lens's own ranking behavior, not a flaw in the pipeline.
- **Multiple faces:** if more than one face is detected in an image, the largest face is automatically treated as the main subject rather than raising an error.
- **Windows + Microsoft Edge only, currently.** The native file-picker automation (`pyautogui`) is written for Windows' file dialog and would need a platform-specific branch to run on macOS or Linux.
- **Requires a visible desktop session.** Because the upload step drives a real on-screen OS dialog, this cannot run headless, over most remote desktop setups, or in CI/CD environments.
- **Dependent on Google's current page structure.** Google Lens is not a public API and its HTML/JS structure can change without notice, which may require selector updates in `src/web_search.py` in the future.
- **Not a production identity-verification system.** This is a technical proof-of-concept demonstrating the full pipeline end to end; a production deployment would need consent handling, rate limiting, and likely an official API (e.g. Google Cloud Vision's Web Detection) instead of browser automation.

---

## Troubleshooting

- **"Blockchain connection failed!"** — Ganache isn't running, or is running on a different port than `7545`. Open Ganache and check the RPC Server address.
- **"Image not found" / file picker says "Path does not exist"** — double-check the exact filename (including case and extension) actually sitting in `data/`, e.g. via `dir data` in PowerShell.
- **"No face detected"** — try a clearer, front-facing photo; heavily stylized or very low-resolution images can fail detection.
- **Google Lens step times out / debug screenshot saved** — check `debug_timeout.png` / `debug_after_attempt.png` generated in the project root; these show exactly what the browser looked like at the moment it failed, which is the fastest way to diagnose a UI change on Google's end.
