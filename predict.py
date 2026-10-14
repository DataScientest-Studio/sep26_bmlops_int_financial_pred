###############################################################
# This script:
#   - loads latest model,
#   - returns prediction for data using latest model,
#   - the data is provided here in the file as EXAMPLE.
###############################################################
# TO DO (see parts with '?'):
#   - add the right paths in the beginning,
#   - create .env file for user name etc. or add github secrets,
#   - change data source (user gives data as input or loaded from somewhere with choices?).
###############################################################

# general
import glob
import os
import joblib
import pandas as pd
from datetime import datetime
# data
from sqlalchemy import create_engine

# load env variables
# username, password, host, port, and database name stored in .env file locally
# use .gitignore so the file is NOT tracked!
from dotenv import load_dotenv
load_dotenv()  # Loads variables from the .env file
# Load credentials securely from environment variables
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST", "localhost")
db_name = os.getenv("DB_NAME")
# ALTERNATIVE: save each variable separetely in github secrets > actions > new repo secret
# connect to postgresql

# dir for model and logs
LOG_FILE = "logs/predict.logs"
MODEL_PATH = "models"

# log functions
def log_message(level, message):
    # function to log messages with timestamps console and log file
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)

# main script
def main():
    log_message("START", "Starting prediction execution.")

    # find the most recent model file in MODEL_PATH
    model_files = glob.glob("models/linear_regression_model_*.pkl")

    if not model_files:
        log_message("ERROR", f"No trained model files found in {MODEL_PATH} directory!")
    # Sort by modification time or filename to get the latest one
    latest_model_path = max(model_files, key=os.path.getmtime)
    log_message("SUCCESS", f"Loading model from: {latest_model_path}")

    # Load model
    try:
        model = joblib.load(latest_model_path)

        # load new data to make predictions on
        # change depending on what this should be?
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
        engine = create_engine(db_url)

        # query data and load into a dataframe
        # change query?
        query = "SELECT stocks, date FROM stock_data;"
        df = pd.read_sql(query, con=engine)
        # check data
        if df.empty:
            log_message("ERROR", f"No data found in the database to predict.")

        # ensure columns match the exact features the model was trained on
        # change variable name?
        X = df["stocks"]
        # drop missing values?
        # predictions
        predictions = model.predict(X)

        # output results
        df["predicted_price"] = predictions
        log_message("PREDICTIONS", f"{df}")

    except Exception as e:
        log_message("ERROR", f"An unexpected error occurred during prediction: {str(e)}")
        exit(1)

    log_message("END", "Prediction finished.")
    log_message("SEPARATOR", "-" * 66)

if __name__ == "__main__":
    main()