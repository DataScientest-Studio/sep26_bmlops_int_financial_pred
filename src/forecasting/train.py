"""Train a linear regression model using data from a PostgreSQL database.

This script:
   - loads stock (or time series) data from postgre sql,
   - creates dataframe with it,
   - creates linear regression model/classifier,
   - trains it on the loaded data,
   - saves trained model as pkl file,
   - creates log messages with status and model metrics.

TO DO (see parts with '?'):
  - add the right paths in the beginning,
  - create .env file for user name etc. or add github secrets.
"""

# paths
import os
from datetime import datetime

# modeling
import joblib
import numpy as np

# data processing
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# data base
from sqlalchemy import create_engine

# important paths for db, model, logs
# needs changes?
PROCESSED_DIR = "db"
MODEL_PATH = "models"
LOG_FILE = "logs/train.logs"


# function for log messages with time stamp
def log_message(level, message):
    """Function to log messages with timestamps console and log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")


def main():
    """Load data, defining model, then train on data."""
    log_message("START", "Starting model training pipeline execution.")

    # check directories exist
    os.makedirs(MODEL_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    try:
        """data loading."""
        # username, password, host, port, and
        # database name stored in .env file locally
        # use .gitignore so the file is NOT tracked!
        from dotenv import load_dotenv

        load_dotenv()  # Loads variables from the .env file
        # Load credentials securely from environment variables
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_name = os.getenv("DB_NAME")
        # ALTERNATIVE: save each variable separetely in github secrets > actions
        # > new repo secret
        # connect to postgresql
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
        engine = create_engine(db_url)

        """data query and preprocessing"""
        # query data and load into a dataframe
        query = "SELECT close_price, date FROM stock_data;"
        df = pd.read_sql(query, con=engine)
        # drop missing values
        df.dropna(inplace=True)
        # check length of dataframe
        if df.empty or len(df) < 5:
            log_message(
                "WARNING", "Dataset is too small or empty for reliable training."
            )
            exit(1)

        log_message("INFO", f"Successfully loaded {len(df)} rows.")

        """modeling part"""
        import warnings

        warnings.filterwarnings("ignore")
        # variables
        X = df.drop(["date"], axis=1)  # explantory variables
        y = df[["close price"]]  # target variable

        # train test split and standardize
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )
        sc = StandardScaler()
        X_train = sc.fit_transform(X_train)
        X_test = sc.transform(X_test)

        # Linear Regression model
        # maybe change to SARIMAX, LSTM or transformers later?
        model = LinearRegression()
        # train
        model.fit(X_train, y_train)
        # predict to calculate metrics
        y_pred = model.predict(X_test)
        # Calculate metrics
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred) if len(set(y_test)) > 1 else 0.0

        log_message(
            "METRICS",
            f"Evaluation Metrics -> RMSE: {rmse:.4f}, MAE: {mae:.4f}, R2: {r2:.4f}",
        )

        """model saving"""
        # generate the current timestamp string
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # filename with timestamp for versioning
        model_filename = f"models/linear_regression_model_{timestamp}.pkl"
        model_filename = os.path.join(MODEL_PATH, model_filename)
        joblib.dump(model, model_filename)

        log_message(
            "SUCCESS",
            f"Base model already exists. Saved new model at {model_filename}.",
        )

    except Exception as e:
        log_message(
            "ERROR", f"An unexpected error occurred during model training: {e!s}"
        )
        exit(1)

    log_message("END", "Model training finished.")
    log_message("SEPARATOR", "-" * 66)


if __name__ == "__main__":
    main()
