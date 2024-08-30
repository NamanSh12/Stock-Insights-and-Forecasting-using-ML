import s3fs
import pandas as pd
from confluent_kafka import Producer
import json

def produce_data():
    s3_bucket = 'stockp'
    s3_key = 'TATAMOTORS.csv'
    kafka_bootstrap_servers = 'localhost:9092'
    kafka_topic = 'your_topic'
    s3_region = 'eu-north-1'

    def delivery_report(err, msg):
        if err is not None:
            return f"Message delivery failed: {err}"
        else:
            return f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"

    producer = None
    try:
        fs = s3fs.S3FileSystem(config_kwargs={'region_name': s3_region})
        producer = Producer({'bootstrap.servers': kafka_bootstrap_servers})

        if fs.exists(f'{s3_bucket}/{s3_key}'):
            with fs.open(f'{s3_bucket}/{s3_key}', 'r') as f:
                df = pd.read_csv(f)

            for index, row in df.head(10).iterrows():
                data = row.to_dict()
                producer.produce(kafka_topic, value=json.dumps(data), callback=delivery_report)

            producer.poll(1)
            return "Data sent to Kafka successfully."
        else:
            return "The specified file does not exist in S3."

    except Exception as e:
        return f"An error occurred: {e}"
    finally:
        if producer:
            producer.flush()
