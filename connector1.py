from confluent_kafka import Consumer
import json
import mysql.connector
from mysql.connector import Error
import math

def connect_mysql():
    kafka_bootstrap_servers = 'localhost:9092'
    kafka_topic = 'your_topic'

    mysql_config = {
        'user': 'root',
        'password': 'naman@1',
        'host': 'localhost',
        'database': 'stock',
        'raise_on_warnings': True
    }

    def sanitize_key(key):
        return key.replace('%', 'Percent_')

    def insert_into_mysql(data):
        try:
            connection = mysql.connector.connect(**mysql_config)
            if connection.is_connected():
                cursor = connection.cursor()
                sanitized_data = {sanitize_key(k): v for k, v in data.items()}

                for key in sanitized_data:
                    if isinstance(sanitized_data[key], float) and math.isnan(sanitized_data[key]):
                        sanitized_data[key] = None

                insert_query = """
                    INSERT INTO stock_data (Date, Symbol, Series, Prev_Close, Open, High, Low, Last, Close, VWAP, Volume, Turnover, Trades, Deliverable_Volume, Percent_Deliverable)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                values = (
                    sanitized_data.get('Date'),
                    sanitized_data.get('Symbol'),
                    sanitized_data.get('Series'),
                    sanitized_data.get('Prev_Close'),
                    sanitized_data.get('Open'),
                    sanitized_data.get('High'),
                    sanitized_data.get('Low'),
                    sanitized_data.get('Last'),
                    sanitized_data.get('Close'),
                    sanitized_data.get('VWAP'),
                    sanitized_data.get('Volume'),
                    sanitized_data.get('Turnover'),
                    sanitized_data.get('Trades'),
                    sanitized_data.get('Deliverable_Volume'),
                    sanitized_data.get('Percent_Deliverable')
                )

                cursor.execute(insert_query, values)
                connection.commit()
                return "Record inserted successfully into MySQL table."

        except Error as e:
            return f"Error: {e}"
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

    consumer = None
    record_count = 0
    max_records = 10

    try:
        consumer = Consumer({
            'bootstrap.servers': kafka_bootstrap_servers,
            'group.id': 'my-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        })
        consumer.subscribe([kafka_topic])

        while record_count < max_records:
            msg = consumer.poll(timeout=30.0)
            if msg is None:
                continue
            if msg.error():
                return f"Error: {msg.error()}"

            data = json.loads(msg.value().decode('utf-8'))
            insert_into_mysql(data)
            record_count += 1

        return f"Inserted {record_count} records into MySQL."

    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        if consumer:
            consumer.close()
