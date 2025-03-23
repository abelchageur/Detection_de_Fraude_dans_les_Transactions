CREATE EXTERNAL TABLE IF NOT EXISTS blacklist (
    customer_id STRING,
    blacklist_reason STRING,
    blacklist_date TIMESTAMP,
    source STRING
)
ROW FORMAT DELIMITED
FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/data/blacklist';