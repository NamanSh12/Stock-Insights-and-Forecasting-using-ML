from flask import Flask, render_template, jsonify
from producer1 import produce_data
from consumer1 import consume_data
from connector1 import connect_mysql
import pandas as pd
import json
from confluent_kafka import Consumer, KafkaException, KafkaError
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import numpy as np
import plotly.express as px
import plotly.graph_objs as go
import plotly.io as pio

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/produce', methods=['POST'])
def produce():
    try:
        result = produce_data()
        return jsonify({'message': result})
    except Exception as e:
        return jsonify({'error': f'An error occurred while producing data: {str(e)}'}), 500

@app.route('/consume', methods=['POST'])
def consume():
    try:
        result = consume_data()
        return jsonify({'message': result})
    except Exception as e:
        return jsonify({'error': f'An error occurred while consuming data: {str(e)}'}), 500

@app.route('/connect', methods=['POST'])
def connect():
    try:
        result = connect_mysql()
        return jsonify({'message': result})
    except Exception as e:
        return jsonify({'error': f'An error occurred while connecting to MySQL: {str(e)}'}), 500

# Kafka Configuration
kafka_bootstrap_servers = 'localhost:9092'
kafka_topic = 'your_topic'


# Kafka Consumer
consumer = Consumer({
    'bootstrap.servers': kafka_bootstrap_servers,
    'group.id': 'my-group',
    'auto.offset.reset': 'earliest'
})
consumer.subscribe([kafka_topic])

def preprocess_data():
    data_points = []

    # Poll Kafka for messages
    try:
        while True:
            msg = consumer.poll(timeout=1.0)  # Shorter timeout for quicker polling
            if msg is None:
                if data_points:
                    break  # Exit if we have received data
                print("No messages received, retrying...")
                continue  # Continue polling

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                elif msg.error():
                    raise KafkaException(msg.error())

            data = json.loads(msg.value().decode('utf-8'))
            data_points.append(data)

            # Commit the offset after processing the message
            consumer.commit()

            # Stop collecting data if a sufficient number of messages is received
            if len(data_points) >= 1000:  # Adjust based on your requirements
                break

    except KafkaException as ke:
        print(f"Kafka exception: {ke}")
    except Exception as e:
        print(f"An error occurred while consuming messages: {e}")
    finally:
        consumer.close()

    # Check if data_points has data
    if not data_points:
        print("No data fetched from Kafka.")
        return pd.DataFrame()

    df = pd.DataFrame(data_points)
    print(df)
    # Check if the DataFrame is empty
    if df.empty:
        print("Fetched data is empty.")
        return df

    # Preprocessing steps
    columns_drop = ['Symbol', 'Series', 'Last', 'VWAP', 'Trades']
    df = df.drop(columns=columns_drop, errors='ignore')
    df = df.dropna()
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df['year'] = df['Date'].dt.year
        df['month'] = df['Date'].dt.month
        df['day'] = df['Date'].dt.day
        df.set_index('Date', inplace=True)
        df.drop(['year', 'month', 'day'], axis=1, inplace=True)
    df = pd.get_dummies(df)

    return df

#@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/train', methods=['POST'])
def train_models():
    df = preprocess_data()
    if df.empty:
        return jsonify({'error': 'No data available for training'}), 500
    
    try:
        metrics, _, y_test, y_pred_linear, _, y_pred_boosting, y_test_lstm, y_pred_lstm = train_models_logic(df)
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 500
    except Exception as e:
        return jsonify({'error': 'An error occurred while training models'}), 500

    # Ensure plots are created and encoded as JSON
    return jsonify({
        'metrics': metrics,
        'lin_reg_fig': create_plot(df.index[-len(y_test):], y_test, y_pred_linear, 'Linear Regression Predictions'),
        'boosting_fig': create_plot(df.index[-len(y_test):], y_test, y_pred_boosting, 'Boosting Predictions'),
        'lstm_fig': create_plot(df.index[-len(y_test_lstm):], y_test_lstm, y_pred_lstm, 'LSTM Predictions')
    })



def train_models_logic(df):
    if 'Close' not in df.columns:
        raise ValueError("DataFrame must contain a 'Close' column for training.")

    X = df.drop('Close', axis=1)
    y = df['Close']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    
    # Linear Regression
    linear_model = LinearRegression()
    linear_model.fit(X_train, y_train)
    y_pred_linear = linear_model.predict(X_test)
    mse_linear = mean_squared_error(y_test, y_pred_linear)
    r2_linear = r2_score(y_test, y_pred_linear)

    # Boosting
    dt = DecisionTreeRegressor(max_depth=1)
    ada_boost = AdaBoostRegressor(estimator=dt, random_state=42)
    ada_boost.fit(X_train, y_train)
    y_pred_boosting = ada_boost.predict(X_test)
    mse_boosting = mean_squared_error(y_test, y_pred_boosting)
    r2_boosting = r2_score(y_test, y_pred_boosting)

    # Standardize data for LSTM
    scaler_X = StandardScaler()
    X_scaled = scaler_X.fit_transform(X)
    scaler_y = StandardScaler()
    y_scaled = scaler_y.fit_transform(y.values.reshape(-1, 1)).flatten()

    time_step = 10
    def create_sequences(data, target, time_step=10):
        X, y = [], []
        for i in range(len(data) - time_step):
            X.append(data[i:i + time_step])
            y.append(target[i + time_step])
        return np.array(X), np.array(y)

    if len(X_scaled) <= time_step:
        raise ValueError("Insufficient data for LSTM sequence creation. Increase data points or reduce time_step.")

    X_seq, y_seq = create_sequences(X_scaled, y_scaled, time_step)
    X_train_seq, X_test_seq, y_train_seq, y_test_seq = train_test_split(X_seq, y_seq, test_size=0.3, random_state=42)

    model = Sequential()
    model.add(LSTM(units=50, activation='relu', input_shape=(time_step, X_train_seq.shape[2])))
    model.add(Dense(1))
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(X_train_seq, y_train_seq, epochs=10, batch_size=32, validation_split=0.3, verbose=1)

    y_pred_lstm = model.predict(X_test_seq)
    y_pred_lstm = scaler_y.inverse_transform(y_pred_lstm).flatten()
    y_test_lstm = scaler_y.inverse_transform(y_test_seq.reshape(-1, 1)).flatten()
    mse_lstm = mean_squared_error(y_test_lstm, y_pred_lstm)
    r2_lstm = r2_score(y_test_lstm, y_pred_lstm)

    return {
        'Linear Regression': {'mse': mse_linear, 'r2': r2_linear},
        'Boosting': {'mse': mse_boosting, 'r2': r2_boosting},
        'LSTM': {'mse': mse_lstm, 'r2': r2_lstm}
    }, df, y_test, y_pred_linear, y_test, y_pred_boosting, y_test_lstm, y_pred_lstm

def create_plot(x, y_true, y_pred, title):
    if len(x) != len(y_true) or len(x) != len(y_pred):
        raise ValueError("Length of x, y_true, and y_pred must be the same for plotting.")
    
    df_plot = pd.DataFrame({
        'Date': x,
        'Actual': y_true,
        'Predicted': y_pred
    })

    if pd.api.types.is_datetime64_any_dtype(df_plot['Date']):
        df_plot['Date'] = pd.to_datetime(df_plot['Date'])
    else:
        df_plot['Date'] = pd.to_datetime(df_plot['Date'], errors='coerce')

    fig = px.line(df_plot, x='Date', y=['Actual', 'Predicted'], labels={'value': 'Close'}, title=title)
    fig.update_layout(xaxis_title='Date', yaxis_title='Close')
    return pio.to_json(fig)

if __name__ == '__main__':
    app.run(debug=False)

