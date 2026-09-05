"""
face-blockchain-verifier - full pipeline
------------------------------------------
Face scan -> Google Lens web/social search (find a real matching post) ->
hash the discovered data -> store it on the local Ganache blockchain ->
re-verify the stored record against a freshly recomputed hash.

This is the single script your screen recording should show running
start to finish.

Run from the project root:
    python src\\pipeline.py
"""

import os
import sys
import hashlib
import time

import cv2
import numpy as np
from insightface.app import FaceAnalysis
from web3 import Web3

# Reuse everything we already built and tested in web_search.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from web_search import (
    build_driver,
    wait_for_modal_ready,
    upload_image_to_lens,
    wait_for_lens_results,
    extract_matches,
    choose_best_match,
    extract_result_text,
)


GANACHE_URL = "http://127.0.0.1:7545"


# --------------------------------------------------------------------------
# Step 1: Face identification (detect + encode)
# --------------------------------------------------------------------------
def encode_face(image_path):
    print("\n[1/4] Detecting and encoding face...")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))

    image = cv2.imread(image_path)
    if image is None:
        print(f"Image not found: {image_path}")
        sys.exit(1)

    faces = app.get(image)
    if len(faces) == 0:
        print("No face detected in the image!")
        sys.exit(1)

    if len(faces) > 1:
        # Not a task requirement to handle multiple people - just pick the
        # largest face (main subject) rather than failing outright, so a
        # busy background doesn't kill the whole run.
        def face_area(f):
            x1, y1, x2, y2 = f.bbox
            return (x2 - x1) * (y2 - y1)

        faces.sort(key=face_area, reverse=True)
        print(f"{len(faces)} faces detected - using the largest one as the main subject.")

    embedding = faces[0].embedding
    print(f"Face encoded successfully. Embedding shape: {embedding.shape}")

    # Optional bonus check: compare against a previously registered face,
    # if one exists (register.py). Not required by the task, but useful.
    registered_path = "data/registered_face.npy"
    if os.path.isfile(registered_path):
        registered = np.load(registered_path)
        similarity = float(
            np.dot(registered, embedding)
            / (np.linalg.norm(registered) * np.linalg.norm(embedding))
        )
        print(f"(Optional) Similarity to registered face: {similarity:.6f}")

    return embedding


# --------------------------------------------------------------------------
# Step 2: Web/social media search via Google Lens
# --------------------------------------------------------------------------
def find_matching_post(image_path):
    print("\n[2/4] Searching the web for a matching post (Google Lens)...")
    driver = build_driver()
    try:
        driver.get("https://lens.google.com/")
        wait_for_modal_ready(driver)

        attached = upload_image_to_lens(driver, image_path)
        if not attached:
            print("Could not attach the image to Google Lens after several attempts.")
            return None

        wait_for_lens_results(driver)
        clicked_tab, matches = extract_matches(driver)

        if not matches:
            print("No external links found in Lens results.")
            fallback_text = extract_result_text(driver)
            return {"url": None, "title": fallback_text[:200], "domain": "none", "raw_fallback": True}

        best = choose_best_match(matches)
        if best.get("url"):
            print(f"Found matching post: [{best['domain']}] {best['url']}")
        else:
            print(f"Found matching post (text-based, no direct link): [{best['domain']}] {best['title'][:80]}")
        return best
    finally:
        driver.quit()


# --------------------------------------------------------------------------
# Step 3: Hash the discovered data (tamper-evident fingerprint)
# --------------------------------------------------------------------------
def hash_discovery(image_path, match, embedding):
    print("\n[3/4] Building tamper-evident fingerprint of the discovery...")
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    payload = (
        image_bytes
        + (match.get("url") or "").encode()
        + (match.get("title") or "").encode()
        + embedding.tobytes()
    )
    digest = hashlib.sha256(payload).hexdigest()
    print(f"SHA-256 fingerprint: {digest}")
    return digest


# --------------------------------------------------------------------------
# Step 4: Store on Ganache, then re-verify by reading it back
# --------------------------------------------------------------------------
def store_and_verify(image_name, match, digest):
    print("\n[4/4] Storing on the local Ganache blockchain...")
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        print("Blockchain connection failed! Is Ganache running?")
        sys.exit(1)

    account = w3.eth.accounts[0]

    match_url_display = match.get("url") or "(text-based match, no direct URL)"
    record_text = (
        f"DISCOVERY | Image: {image_name} | "
        f"MatchSource: {match.get('domain')} | "
        f"MatchURL: {match_url_display} | "
        f"MatchTitle: {(match.get('title') or '')[:100]} | "
        f"SHA256: {digest}"
    )
    data = w3.to_hex(text=record_text)

    transaction = {
        "from": account,
        "to": account,
        "value": 0,
        "gas": 200000,
        "gasPrice": w3.to_wei(1, "gwei"),
        "nonce": w3.eth.get_transaction_count(account),
        "data": data,
    }

    tx_hash = w3.eth.send_transaction(transaction)
    print("Transaction sent:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Transaction confirmed in block:", receipt.blockNumber)

    # --- Re-verification: read the record back from the chain and check
    #     it still contains the same fingerprint we computed. ---
    print("\nRe-verifying stored record against the chain...")
    stored_tx = w3.eth.get_transaction(tx_hash)
    stored_text = bytes(stored_tx["input"]).decode("utf-8")
    print("Stored on-chain record:", stored_text)

    if digest in stored_text:
        print("\nRE-VERIFICATION RESULT: MATCH - the on-chain record matches the fingerprint we just computed.")
    else:
        print("\nRE-VERIFICATION RESULT: MISMATCH - something is wrong, the stored record doesn't contain our fingerprint.")

    return tx_hash.hex(), receipt.blockNumber


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    print("====================================")
    print(" FACE -> WEB SEARCH -> BLOCKCHAIN PIPELINE")
    print("====================================")

    image_name = input("\nEnter image name (in data/ folder): ").strip()
    image_path = os.path.abspath(os.path.join("data", image_name))

    if not os.path.isfile(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    embedding = encode_face(image_path)

    match = find_matching_post(image_path)
    if match is None:
        print("\nPipeline stopped: could not complete the web search step.")
        sys.exit(1)

    digest = hash_discovery(image_path, match, embedding)
    tx_hash, block_number = store_and_verify(image_name, match, digest)

    match_display = match.get("url") or f"[{match.get('domain')}] {match.get('title')}"

    print("\n====================================")
    print(" PIPELINE COMPLETE")
    print("====================================")
    print(f"Image:        {image_name}")
    print(f"Matched post: {match_display}")
    print(f"Fingerprint:  {digest}")
    print(f"Tx hash:      {tx_hash}")
    print(f"Block:        {block_number}")


if __name__ == "__main__":
    main()