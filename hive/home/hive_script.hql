CREATE EXTERNAL TABLE IF NOT EXISTS transactions (
    amount STRING   ,
    currency STRING,
    customer_id STRING, 
    date_time STRING,
    location STRING,
    merchant_details STRING,
    transaction_id STRING,
    transaction_type STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/transactions';

CREATE EXTERNAL TABLE IF NOT EXISTS customers (
    customer_id STRING,
    age STRING,
    location STRING,
    avg_transaction_value STRING,
    account_history STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/customers';

CREATE EXTERNAL TABLE IF NOT EXISTS external_data (
    customer_id STRING,
    fraud_report STRING,
    credit_score STRING

)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/external_data';

CREATE EXTERNAL TABLE IF NOT EXISTS blacklist (
    customer_id STRING,
    blacklist_reason STRING,
    blacklist_date STRING,
    source STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/blacklist';