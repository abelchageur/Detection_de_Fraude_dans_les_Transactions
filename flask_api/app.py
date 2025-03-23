# from flask import Flask, jsonify  # Corrected import
# import json

# app = Flask(__name__)

# # Load data from the JSON files
# with open("transactions.json", "r") as f:
#     transactions = json.load(f)

# with open("customers.json", "r") as f:
#     customers = json.load(f)

# with open("external_data.json", "r") as f:
#     external_data = json.load(f)

# @app.route("/api/transactions", methods=["GET"])
# def get_transactions():
#     return jsonify(transactions)

# @app.route("/api/customers", methods=["GET"])
# def get_customers():
#     return jsonify(customers)

# @app.route("/api/external_data", methods=["GET"])
# def get_external_data():
#     return jsonify(external_data)

# if __name__ == "__main__":
#     app.run(debug=True)
from flask import Flask, jsonify
import random
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)

# Global variables to store generated data
transactions = []
customers = []
external_data = {}

# Lock for thread-safe updates
data_lock = threading.Lock()

def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def generate_high_frequency_transactions(customer_id, start_date, num_transactions):
    transactions = []
    for _ in range(num_transactions):
        transactions.append({
            "transaction_id": f"T{random.randint(10000, 99999)}",
            "date_time": random_date(start_date, start_date + timedelta(days=1)).isoformat(),
            "amount": random.uniform(10, 1000),
            "currency": random.choice(["USD", "EUR", "GBP"]),
            "merchant_details": f"Merchant{random.randint(1, 20)}",
            "customer_id": customer_id,
            "transaction_type": random.choice(["purchase", "withdrawal"]),
            "location": f"City{random.randint(11, 20)}"
        })
    return transactions

def generate_data(num_transactions, num_customers):
    global transactions, customers, external_data

    new_customers = []
    new_transactions = []
    new_external_data = {
        "blacklist_info": [f"Merchant{random.randint(21, 30)}" for _ in range(10)],
        "credit_scores": {},
        "fraud_reports": {}
    }

    for i in range(num_customers):
        customer_id = f"C{i:03}"
        customer_city = f"City{random.randint(1, 10)}"
        new_customers.append({
            "customer_id": customer_id,
            "account_history": [],
            "demographics": {"age": random.randint(18, 70), "location": customer_city},
            "behavioral_patterns": {"avg_transaction_value": random.uniform(50, 500)}
        })
        new_external_data["credit_scores"][customer_id] = random.randint(300, 850)
        new_external_data["fraud_reports"][customer_id] = random.randint(0, 5)

    for i in range(num_transactions):
        customer_id = f"C{random.randint(0, num_customers-1):03}"
        transaction = {
            "transaction_id": f"T{i:05}",
            "date_time": random_date(datetime(2020, 1, 1), datetime(2023, 1, 1)).isoformat(),
            "amount": random.uniform(10, 1000) * (10 if random.random() < 0.4 else 1),
            "currency": random.choice(["USD", "EUR", "GBP"]),
            "merchant_details": f"Merchant{random.randint(1, 20)}",
            "customer_id": customer_id,
            "transaction_type": random.choice(["purchase", "withdrawal"]),
            "location": f"City{random.randint(1, 10)}"
        }
        new_transactions.append(transaction)
        for customer in new_customers:
            if customer['customer_id'] == customer_id:
                customer['account_history'].append(transaction['transaction_id'])
                break

    for customer in random.sample(new_customers, num_customers // 40):
        new_transactions.extend(generate_high_frequency_transactions(customer['customer_id'], datetime(2022, 1, 1), 10))

    # Update global data with thread-safe locking
    with data_lock:
        transactions = new_transactions
        customers = new_customers
        external_data = new_external_data

def update_data_periodically():
    while True:
        generate_data(1000, 100)  # Generate 1000 transactions and 100 customers
        print("Data updated at:", datetime.now())
        time.sleep(15)  # Update data every 15 seconds

# Start the background thread to update data periodically
update_thread = threading.Thread(target=update_data_periodically)
update_thread.daemon = True
update_thread.start()

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    with data_lock:
        return jsonify(transactions)

@app.route("/api/customers", methods=["GET"])
def get_customers():
    with data_lock:
        return jsonify(customers)

@app.route("/api/external_data", methods=["GET"])
def get_external_data():
    with data_lock:
        return jsonify(external_data)

if __name__ == "__main__":
    app.run(debug=True)