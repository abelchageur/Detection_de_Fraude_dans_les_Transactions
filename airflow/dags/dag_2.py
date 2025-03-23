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
import json

# Load variables from Airflow Variables
email_credentials = Variable.get("email_credentials", deserialize_json=True)
paths = Variable.get("paths", deserialize_json=True)
api_endpoints = Variable.get("api_endpoints", deserialize_json=True)
docker_commands = Variable.get("docker_commands", deserialize_json=True)

# Extract values
EMAIL = email_credentials.get("email")
EMAIL_PASSWORD = email_credentials.get("password")
HDFS_TRANSACTIONS_PATH = paths.get("hdfs_transactions_path")
HDFS_CUSTOMERS_PATH = paths.get("hdfs_customers_path")
HDFS_EXTERNAL_DATA_PATH = paths.get("hdfs_external_data_path")
HDFS_BLACKLIST_PATH = paths.get("hdfs_blacklist_path")
LOCAL_TRANSACTIONS_PATH = paths.get("local_transactions_path")
LOCAL_CUSTOMERS_PATH = paths.get("local_customers_path")
LOCAL_EXTERNAL_DATA_PATH = paths.get("local_external_data_path")
LOCAL_BLACKLIST_PATH = paths.get("local_blacklist_path")
HIVE_SCRIPT_PATH = paths.get("hive_script_path")
TRANSACTIONS_API = api_endpoints.get("transactions")
CUSTOMERS_API = api_endpoints.get("customers")
EXTERNAL_DATA_API = api_endpoints.get("external_data")
DOCKER_CP = docker_commands.get("cp")
DOCKER_EXEC = docker_commands.get("exec")

# Define default arguments for the DAG
def notify_failure(context):
    task_instance = context['task_instance']
    email = context['params'].get('email', EMAIL)  # Use the email from Airflow Variables
    subject = f"Task Failed: {task_instance.task_id}"
    html_content = f"""
    Task {task_instance.task_id} failed.
    Error: {context.get('exception')}
    """
    send_email(to=email, subject=subject, html_content=html_content)

def notify_success(context):
    task_instance = context['task_instance']
    email = context['params'].get('email', EMAIL)  # Use the email from Airflow Variables
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
    'email': [EMAIL],  # Use the email from Airflow Variables
    'on_failure_callback': notify_failure,
    'on_success_callback': notify_success,
}

# Define the DAG
dag = DAG(
    'fraud_detection_pipeline_2',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
    params={
        'email': EMAIL,  # Use the email from Airflow Variables
    },
)

# Task 1: Fetch data from APIs
def fetch_data(**kwargs):
    # Fetch transaction data
    transactions = requests.get(TRANSACTIONS_API).json()
    print(f"Transactions data: {transactions}")

    # Fetch customer data
    customers = requests.get(CUSTOMERS_API).json()
    print(f"Customers data: {customers}")

    # Fetch external data
    external_data_response = requests.get(EXTERNAL_DATA_API)
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
        write_to_csv(transactions, LOCAL_TRANSACTIONS_PATH, fieldnames=transactions[0].keys())
        kwargs['ti'].xcom_push(key='transactions_path', value=LOCAL_TRANSACTIONS_PATH)
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
        
        write_to_csv(flattened_customers, LOCAL_CUSTOMERS_PATH, fieldnames=flattened_customers[0].keys())
        kwargs['ti'].xcom_push(key='customers_path', value=LOCAL_CUSTOMERS_PATH)
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
        write_to_csv(flattened_data, LOCAL_EXTERNAL_DATA_PATH, fieldnames=["customer_id", "credit_score", "fraud_report"])
        kwargs['ti'].xcom_push(key='external_data_path', value=LOCAL_EXTERNAL_DATA_PATH)
    else:
        print("External data is empty or not structured as expected. Skipping CSV creation.")

fetch_data_task = PythonOperator(
    task_id='fetch_data',
    python_callable=fetch_data,
    provide_context=True,
    dag=dag,
)

# Task 2: Store data in HDFS
store_data_hdfs_task = BashOperator(
    task_id='store_data_hdfs',
    bash_command=(
        f'{DOCKER_CP} {{{{ ti.xcom_pull(task_ids="fetch_data", key="transactions_path") }}}} namenode:{{{{ ti.xcom_pull(task_ids="fetch_data", key="transactions_path") }}}} && '
        f'{DOCKER_CP} {{{{ ti.xcom_pull(task_ids="fetch_data", key="customers_path") }}}} namenode:{{{{ ti.xcom_pull(task_ids="fetch_data", key="customers_path") }}}} && '
        f'{DOCKER_CP} {{{{ ti.xcom_pull(task_ids="fetch_data", key="external_data_path") }}}} namenode:{{{{ ti.xcom_pull(task_ids="fetch_data", key="external_data_path") }}}} && '
        f'{DOCKER_EXEC} namenode bash -c "'
        f'hdfs dfs -mkdir -p {HDFS_TRANSACTIONS_PATH} && '
        f'hdfs dfs -mkdir -p {HDFS_CUSTOMERS_PATH} && '
        f'hdfs dfs -mkdir -p {HDFS_EXTERNAL_DATA_PATH} && '
        f'hdfs dfs -put -f {{{{ ti.xcom_pull(task_ids="fetch_data", key="transactions_path") }}}} {HDFS_TRANSACTIONS_PATH}/transactions.csv && '
        f'hdfs dfs -put -f {{{{ ti.xcom_pull(task_ids="fetch_data", key="customers_path") }}}} {HDFS_CUSTOMERS_PATH}/customers.csv && '
        f'hdfs dfs -put -f {{{{ ti.xcom_pull(task_ids="fetch_data", key="external_data_path") }}}} {HDFS_EXTERNAL_DATA_PATH}/external_data.csv && '
        f'rm -rf {{{{ ti.xcom_pull(task_ids="fetch_data", key="transactions_path") }}}} {{{{ ti.xcom_pull(task_ids="fetch_data", key="customers_path") }}}} {{{{ ti.xcom_pull(task_ids="fetch_data", key="external_data_path") }}}}"'
    ),
    dag=dag,
)

# Task 3: Load data into Hive
load_data_hive_task = BashOperator(
    task_id='load_data_hive',
    bash_command=f'{DOCKER_EXEC} hive hive -f {HIVE_SCRIPT_PATH}',
    dag=dag,
)

# Task 4: Populate blacklist table
def populate_blacklist(**kwargs):
    import requests
    import subprocess
    import logging
    from datetime import datetime

    logging.info("Fetching blacklist data from API...")
    response = requests.get(EXTERNAL_DATA_API)
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
    with open(LOCAL_BLACKLIST_PATH, "w") as f:
        f.write("customer_id,blacklist_reason,blacklist_date,source\n")
        for entry in blacklist_data:
            logging.info(f"Processing entry: {entry}")  # Log each entry
            f.write(f"{entry['customer_id']},{entry['blacklist_reason']},{entry['blacklist_date']},{entry['source']}\n")

    # Upload the file to HDFS
    subprocess.run([
        "docker", "cp", LOCAL_BLACKLIST_PATH, f"namenode:{HDFS_BLACKLIST_PATH}"
    ])
    subprocess.run([
        "docker", "exec", "namenode", "bash", "-c",
        f"hdfs dfs -mkdir -p {HDFS_BLACKLIST_PATH} && "
        f"hdfs dfs -put -f {HDFS_BLACKLIST_PATH} {HDFS_BLACKLIST_PATH}/blacklist.csv && "
        f"rm -rf {LOCAL_BLACKLIST_PATH}"
    ])

    # Load the data into the blacklist table
    subprocess.run([
        "docker", "exec", "hive", "hive", "-e",
        f"LOAD DATA INPATH '{HDFS_BLACKLIST_PATH}/blacklist.csv' INTO TABLE blacklist"
    ])

    kwargs['ti'].xcom_push(key='blacklist_path', value=LOCAL_BLACKLIST_PATH)

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