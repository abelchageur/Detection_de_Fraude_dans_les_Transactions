from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.models import Variable
from airflow.utils.email import send_email
from airflow.utils.dates import days_ago
from datetime import datetime, timedelta
import requests
import subprocess
import csv
import logging

# Define default arguments for the DAG
def notify_failure(context):
    task_instance = context['task_instance']
    email = context['params'].get('email', 'abelchaguerm@gmail.com')  # Fallback email
    subject = f"Task Failed: {task_instance.task_id}"
    html_content = f"""
    Task {task_instance.task_id} failed.
    Error: {context.get('exception')}
    """
    send_email(to=email, subject=subject, html_content=html_content)

def notify_success(context):
    task_instance = context['task_instance']
    email = context['params'].get('email', 'abelchaguerm@gmail.com')  # Fallback email
    subject = f"Task Succeeded: {task_instance.task_id}"
    html_content = f"Task {task_instance.task_id} succeeded."
    send_email(to=email, subject=subject, html_content=html_content)

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email_on_failure': True,
    'email_on_retry': True,
    'email': ['abelchaguermohamed@gmail.com'],  # Default email
    'on_failure_callback': notify_failure,
    'on_success_callback': notify_success,
}

# Define the DAG
dag = DAG(
    'fraud_detection_pipeline',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
    params={
        'email': 'abelchaguerm@gmail.com',  # Default email (can be overridden)
    },
)

# Task 1: Fetch data from APIs
def fetch_data(**kwargs):
    # Fetch transaction data
    transactions = requests.get("http://flask_api:5000/api/transactions").json()
    print(f"Transactions data: {transactions}")

    # Fetch customer data
    customers = requests.get("http://flask_api:5000/api/customers").json()
    print(f"Customers data: {customers}")

    # Fetch external data
    external_data_response = requests.get("http://flask_api:5000/api/external_data")
    print(f"External data response status code: {external_data_response.status_code}")
    print(f"External data response content: {external_data_response.text}")
    external_data = external_data_response.json()

    # Helper function to write JSON data to CSV
    def write_to_csv(data, file_path, fieldnames):
        with open(file_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    # Save transactions to CSV
    if isinstance(transactions, list) and transactions:
        transactions_path = "/tmp/transactions.csv"
        write_to_csv(transactions, transactions_path, fieldnames=transactions[0].keys())
        kwargs['ti'].xcom_push(key='transactions_path', value=transactions_path)
    else:
        print("Transactions data is empty or not a list. Skipping CSV creation.")

    # Save customers to CSV
    if isinstance(customers, list) and customers:
        # Flatten the customers data
        flattened_customers = []
        for customer in customers:
            flattened_customer = {
                "customer_id": customer["customer_id"],
                "age": customer["demographics"]["age"],
                "location": customer["demographics"]["location"],
                "avg_transaction_value": customer["behavioral_patterns"]["avg_transaction_value"],
                "account_history": ";".join(customer["account_history"])  # Join list into a string
            }
            flattened_customers.append(flattened_customer)
        
        customers_path = "/tmp/customers.csv"
        write_to_csv(flattened_customers, customers_path, fieldnames=flattened_customers[0].keys())
        kwargs['ti'].xcom_push(key='customers_path', value=customers_path)
    else:
        print("Customers data is empty or not a list. Skipping CSV creation.")

    # Save external data to CSV
    if isinstance(external_data, dict) and "credit_scores" in external_data and "fraud_reports" in external_data:
        # Flatten the external_data into rows
        flattened_data = []
        for customer_id, credit_score in external_data["credit_scores"].items():
            fraud_report = external_data["fraud_reports"].get(customer_id, None)
            flattened_data.append({
                "customer_id": customer_id,
                "credit_score": credit_score,
                "fraud_report": fraud_report
            })

        # Write the flattened data to CSV
        external_data_path = "/tmp/external_data.csv"
        write_to_csv(flattened_data, external_data_path, fieldnames=["customer_id", "credit_score", "fraud_report"])
        kwargs['ti'].xcom_push(key='external_data_path', value=external_data_path)
    else:
        print("External data is empty or not structured as expected. Skipping CSV creation.")

fetch_data_task = PythonOperator(
    task_id='fetch_data',
    python_callable=fetch_data,
    provide_context=True,
    dag=dag,
)

# Task 2: Store data in HDFS
def store_data_hdfs(**kwargs):
    ti = kwargs['ti']
    transactions_path = ti.xcom_pull(task_ids='fetch_data', key='transactions_path')
    customers_path = ti.xcom_pull(task_ids='fetch_data', key='customers_path')
    external_data_path = ti.xcom_pull(task_ids='fetch_data', key='external_data_path')

    subprocess.run([
        'docker', 'cp', transactions_path, 'namenode:/tmp/transactions.csv'
    ])
    subprocess.run([
        'docker', 'cp', customers_path, 'namenode:/tmp/customers.csv'
    ])
    subprocess.run([
        'docker', 'cp', external_data_path, 'namenode:/tmp/external_data.csv'
    ])
    subprocess.run([
        'docker', 'exec', 'namenode', 'bash', '-c',
        'hdfs dfs -mkdir -p /data/transactions && '
        'hdfs dfs -mkdir -p /data/customers && '
        'hdfs dfs -mkdir -p /data/external_data && '
        'hdfs dfs -put -f /tmp/transactions.csv /data/transactions/transactions.csv && '
        'hdfs dfs -put -f /tmp/customers.csv /data/customers/customers.csv && '
        'hdfs dfs -put -f /tmp/external_data.csv /data/external_data/external_data.csv && '
        'rm -rf /tmp/transactions.csv /tmp/customers.csv /tmp/external_data.csv'
    ])

store_data_hdfs_task = PythonOperator(
    task_id='store_data_hdfs',
    python_callable=store_data_hdfs,
    provide_context=True,
    dag=dag,
)

# Task 3: Load data into Hive
load_data_hive_task = BashOperator(                               
    task_id='load_data_hive',                                     
    bash_command='docker exec hive hive -f /home/hive_script.hql',
    dag=dag,
)

# Task 4: Populate blacklist table
def populate_blacklist(**kwargs):
    import requests
    import subprocess
    import logging
    from datetime import datetime

    logging.info("Fetching blacklist data from API...")
    response = requests.get("http://flask_api:5000/api/external_data")
    logging.info(f"API Response: {response.text}")  # Log the raw response

    try:
        external_data = response.json()  # Parse the response as JSON
        logging.info(f"Parsed JSON: {external_data}")  # Log the parsed JSON
    except ValueError as e:
        logging.error(f"Failed to parse JSON: {e}")
        raise

    # Transform the external_data into a list of blacklist entries
    blacklist_data = []
    for customer_id, fraud_reports in external_data.get("fraud_reports", {}).items():
        if fraud_reports > 3:  # Add to blacklist if fraud reports > 3
            blacklist_entry = {
                "customer_id": customer_id,
                "blacklist_reason": "high_fraud_reports",
                "blacklist_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "external_api"
            }
            blacklist_data.append(blacklist_entry)

    # Save the data to a CSV file
    blacklist_path = "/tmp/blacklist.csv"
    with open(blacklist_path, "w") as f:
        f.write("customer_id,blacklist_reason,blacklist_date,source\n")
        for entry in blacklist_data:
            logging.info(f"Processing entry: {entry}")  # Log each entry
            f.write(f"{entry['customer_id']},{entry['blacklist_reason']},{entry['blacklist_date']},{entry['source']}\n")

    # Upload the file to HDFS
    subprocess.run([
        "docker", "cp", blacklist_path, "namenode:/tmp/blacklist.csv"
    ])
    subprocess.run([
        "docker", "exec", "namenode", "bash", "-c",
        "hdfs dfs -mkdir -p /data/blacklist && "
        "hdfs dfs -put -f /tmp/blacklist.csv /data/blacklist/blacklist.csv && "
        "rm -rf /tmp/blacklist.csv"
    ])

    # Load the data into the blacklist table
    subprocess.run([
        "docker", "exec", "hive", "hive", "-e",
        "LOAD DATA INPATH '/data/blacklist/blacklist.csv' INTO TABLE blacklist"
    ])

    kwargs['ti'].xcom_push(key='blacklist_path', value=blacklist_path)

populate_blacklist_task = PythonOperator(
    task_id='populate_blacklist',
    python_callable=populate_blacklist,
    provide_context=True,
    dag=dag,
)

# Task 5: Run fraud detection queries
def run_fraud_detection(**kwargs):
    # Define the HiveQL query
    query = """
    -- Rule 1: High Transaction Amount
    SELECT * FROM transactions
    WHERE amount > 10000

    UNION ALL

    -- Rule 2: High Transaction Frequency
    SELECT t.*
    FROM transactions t
    JOIN (
        SELECT customer_id, COUNT(*) as transaction_count
        FROM transactions
        WHERE transaction_date >= DATE_SUB(CURRENT_TIMESTAMP, INTERVAL 1 HOUR)
        GROUP BY customer_id
        HAVING transaction_count > 5
    ) high_freq ON t.customer_id = high_freq.customer_id

    UNION ALL

    -- Rule 3: Blacklisted Customers
    SELECT t.*
    FROM transactions t
    JOIN blacklist b ON t.customer_id = b.customer_id
    """

    # Execute the query and save results
    result = subprocess.run([
        "docker", "exec", "hive", "hive", "-e", query
    ], capture_output=True, text=True)

    # Save suspicious transactions to a file (or database)
    suspicious_transactions_path = "/tmp/suspicious_transactions.csv"
    with open(suspicious_transactions_path, "w") as f:
        f.write(result.stdout)

    # Log the results (optional)
    print("Suspicious Transactions Detected:")
    print(result.stdout)

    kwargs['ti'].xcom_push(key='suspicious_transactions_path', value=suspicious_transactions_path)

fraud_detection_task = PythonOperator(
    task_id='run_fraud_detection',
    python_callable=run_fraud_detection,
    provide_context=True,
    dag=dag,
)

# Task 6: Generate alerts
def generate_alerts(**kwargs):
    ti = kwargs['ti']
    suspicious_transactions_path = ti.xcom_pull(task_ids='run_fraud_detection', key='suspicious_transactions_path')

    # Read suspicious transactions from the file
    with open(suspicious_transactions_path, "r") as f:
        suspicious_transactions = f.read()

    # Log the suspicious transactions (or send alerts)
    print("Suspicious Transactions:")
    print(suspicious_transactions)

    # Optionally, save the results to a database or send alerts via email/Slack
    # Example: Save to a database
    # db.save(suspicious_transactions)

generate_alerts_task = PythonOperator(
    task_id='generate_alerts',
    python_callable=generate_alerts,
    provide_context=True,
    dag=dag,
)

# Define task dependencies
fetch_data_task >> store_data_hdfs_task >> load_data_hive_task >> populate_blacklist_task >> fraud_detection_task >> generate_alerts_task