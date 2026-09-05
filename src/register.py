import cv2
import numpy as np
from insightface.app import FaceAnalysis

app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(ctx_id=0, det_size=(640, 640))

# Ask for image
image_name = input("Enter image name to register: ")

image = cv2.imread("data/" + image_name)

if image is None:
    print("Image not found!")
    exit()

# Detect face
faces = app.get(image)

if len(faces) == 0:
    print("No face detected!")
    exit()

if len(faces) > 1:
    print("Multiple faces detected!")
    print("Please use an image containing only one face.")
    exit()

print("Face detected in", image_name)

# Get face embedding
embedding = faces[0].embedding

# Save registered embedding
np.save("data/registered_face.npy", embedding)

print("Face embedding saved successfully!")
print("Registered image:", image_name)