import pandas as pd
from preprocessing import preprocess_jobs
from feature_extraction import extract_features
from analysis import calculate_ctr

df = pd.read_csv("../data/raw_jobs.csv")

df = preprocess_jobs(df)

features = df["job_description"].apply(extract_features).apply(pd.Series)

df = pd.concat([df, features], axis=1)

df = calculate_ctr(df)

df.to_csv("../data/processed_jobs.csv", index=False)

print("Pipeline completed successfully.")
