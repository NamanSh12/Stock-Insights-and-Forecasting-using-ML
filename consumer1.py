from confluent_kafka import Consumer
import pandas as pd
import json

def consume_data():
    kafka_bootstrap_servers = 'localhost:9092'
    kafka_topic = 'your_topic'
    max_messages = 10  # Define the maximum number of messages to consume

    consumer = None
    data_points = []
    message_count = 0

    try:
        consumer = Consumer({
            'bootstrap.servers': kafka_bootstrap_servers,
            'group.id': 'my-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': False
        })
        consumer.subscribe([kafka_topic])

        while message_count < max_messages:
            msg = consumer.poll(timeout=30.0)
            if msg is None:
                continue
            if msg.error():
                return f"Error: {msg.error()}"

            data = json.loads(msg.value().decode('utf-8'))
            data_points.append(data)
            message_count += 1  # Increment the message counter
            print(f"Received message: {data}")

        consumer.close()

        if data_points:
            df = pd.DataFrame(data_points)
            return f"DataFrame constructed from {message_count} Kafka messages."
        else:
            return "No messages received from Kafka."

    except Exception as e:
        return f"An error occurred: {e}"

# Example usage
if __name__ == "__main__":
    result = consume_data()
    print(result)
