import cv2
import numpy as np
from insightface.app import FaceAnalysis

def compare_faces(embedding1, embedding2):
    similarity = np.dot(embedding1, embedding2) / (
        np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
    )
    return similarity

def verify_faces(embedding1, embedding2, threshold=0.6):
    similarity = compare_faces(embedding1, embedding2)

    if similarity >= threshold:
        result = "MATCH"
    else:
        result = "NO MATCH"

    return similarity, result

# Create the face analysis model
app = FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

# Prepare the model
app.prepare(ctx_id=0, det_size=(640, 640))

def get_embedding(image):
    faces = app.get(image)

    if len(faces) == 0:
        print("No face detected.")
        return None, faces

    return faces[0].embedding, faces
# Read our test image
image = cv2.imread("data/test.jpg")
image2 = cv2.imread("data/test2.jpg")

# Detect faces
embedding_test, faces = get_embedding(image)
embedding_test2, faces2 = get_embedding(image2)

print("Faces in test.jpg:", len(faces))
print("Faces in test2.jpg:", len(faces2))

if embedding_test is None or embedding_test2 is None:
    print("Verification cannot be performed.")
    exit()


embedding1 = embedding_test
embedding2 = embedding_test2
similarity, result = verify_faces(embedding1, embedding2)

print("Cosine similarity:", similarity)
print("Result for test.jpg vs test2.jpg:", result)

print("Embedding 1 shape:", embedding1.shape)
print("Embedding 2 shape:", embedding2.shape)
print("Number of faces detected:", len(faces))

# Show information about each detected face
for i, face in enumerate(faces):
    print(f"\nFace {i + 1}")
    print("Bounding box:", face.bbox)
    print("Detection confidence:", face.det_score)
    print("Embedding shape:", face.embedding.shape)
    print("First 10 embedding values:", face.embedding[:10])

    # Draw a box around each detected face
for face in faces:
    x1, y1, x2, y2 = face.bbox.astype(int)

    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

# Resize image for display
display_image = cv2.resize(image, (600, 800))

cv2.imshow("Detected Face", display_image)
cv2.waitKey(0)
cv2.destroyAllWindows()