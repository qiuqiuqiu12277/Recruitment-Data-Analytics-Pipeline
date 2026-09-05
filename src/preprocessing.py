import pandas as pd

def preprocess_jobs(df):
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.drop_duplicates()
    text_cols = df.select_dtypes(include="object").columns
    df[text_cols] = df[text_cols].fillna("")
    return df
