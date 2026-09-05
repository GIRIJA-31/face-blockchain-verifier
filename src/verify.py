import cv2
import numpy as np
from insightface.app import FaceAnalysis
from web3 import Web3


# -----------------------------
# FACE VERIFICATION
# -----------------------------

app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(ctx_id=0, det_size=(640, 640))


# Load registered face
registered_embedding = np.load("data/registered_face.npy")


# Ask user for image
image_name = input("Enter image name: ")

image = cv2.imread("data/" + image_name)

if image is None:
    print("Image not found!")
    exit()


# Detect face
faces = app.get(image)

if len(faces) == 0:
    print("No face detected in", image_name)
    exit()


print("Face detected in", image_name)


# Get embedding
test_embedding = faces[0].embedding


# Calculate cosine similarity
similarity = np.dot(
    registered_embedding,
    test_embedding
) / (
    np.linalg.norm(registered_embedding)
    * np.linalg.norm(test_embedding)
)


print("Cosine similarity:", similarity)


# Threshold
threshold = 0.6


# Determine result
if similarity >= threshold:
    result = "MATCH"
else:
    result = "NO MATCH"


print("Result:", result)


# -----------------------------
# BLOCKCHAIN
# -----------------------------

w3 = Web3(
    Web3.HTTPProvider("http://127.0.0.1:7545")
)


if not w3.is_connected():
    print("Blockchain connection failed!")
    exit()


print("Connected to blockchain!")


# Get Ganache account
account = w3.eth.accounts[0]


# Store verification result
verification_data = (
    f"Face Verification | "
    f"Image: {image_name} | "
    f"Result: {result} | "
    f"Similarity: {similarity:.6f}"
)


# Convert text to hexadecimal
data = w3.to_hex(text=verification_data)


# Create transaction
transaction = {
    "from": account,
    "to": account,
    "value": 0,
    "gas": 100000,
    "gasPrice": w3.to_wei(1, "gwei"),
    "nonce": w3.eth.get_transaction_count(account),
    "data": data
}


# Send transaction
tx_hash = w3.eth.send_transaction(transaction)


print("Blockchain transaction sent!")
print("Transaction hash:", tx_hash.hex())


# Wait for confirmation
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)


print("Blockchain transaction confirmed!")
print("Block number:", receipt.blockNumber)