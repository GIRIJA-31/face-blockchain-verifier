from web3 import Web3

# Connect to Ganache
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))

if not w3.is_connected():
    print("Blockchain connection failed!")
    exit()

print("Connected to blockchain!")
print("Chain ID:", w3.eth.chain_id)

# Get first Ganache account
account = w3.eth.accounts[0]

print("Account:", account)

print(
    "Balance:",
    w3.from_wei(w3.eth.get_balance(account), "ether"),
    "ETH"
)

# Get latest block
latest_block = w3.eth.block_number

print("Latest block:", latest_block)

# Read every block
for block_number in range(1, latest_block + 1):

    block = w3.eth.get_block(block_number)

    print("\n-----------------------------")
    print("Block:", block_number)
    print("Transactions:", len(block.transactions))

    # Read every transaction in the block
    for tx_hash in block.transactions:

        tx = w3.eth.get_transaction(tx_hash)

        print("Transaction:", tx_hash.hex())

        # Read stored transaction data
        if tx["input"] != "0x":

            try:
                data = bytes(tx["input"]).decode("utf-8")
                print("Stored data:", data)

            except UnicodeDecodeError:
                print("Stored data: [binary data]")