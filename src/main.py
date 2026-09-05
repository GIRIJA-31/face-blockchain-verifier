import subprocess
import sys

print("====================================")
print("     FACE BLOCKCHAIN VERIFIER")
print("====================================")

print()
print("1. Register Face")
print("2. Verify Face")
print("3. View Blockchain Records")
print("4. Full Pipeline (Face -> Web Search -> Blockchain)")
print("5. Exit")

choice = input("\nEnter your choice: ")

print()

if choice == "1":
    print("Register Face selected")
    subprocess.run([sys.executable, "src/register.py"])

elif choice == "2":
    print("Verify Face selected")
    subprocess.run([sys.executable, "src/verify.py"])

elif choice == "3":
    print("View Blockchain Records selected")
    subprocess.run([sys.executable, "src/blockchain.py"])

elif choice == "4":
    print("Full Pipeline selected")
    subprocess.run([sys.executable, "src/pipeline.py"])

elif choice == "5":
    print("Exiting...")

else:
    print("Invalid choice")