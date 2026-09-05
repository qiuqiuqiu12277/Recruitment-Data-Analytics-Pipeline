# Recruitment Data Analytics Pipeline

An end-to-end recruitment analytics pipeline that transforms unstructured job descriptions into structured features using Python-based preprocessing and rule-based text mining.

## Motivation

Recruitment data contains valuable information hidden in unstructured job descriptions. This project demonstrates how data processing and feature engineering techniques can convert raw recruitment information into analytical datasets.

## Pipeline

Raw Recruitment Data  
↓  
Data Cleaning & Preprocessing  
↓  
Regex-based Feature Extraction  
↓  
Structured Recruitment Features  
↓  
Exploratory Data Analysis

## Key Features

- Data preprocessing with pandas
- Duplicate removal and missing value handling
- Regex-based experience extraction
- Rule-based technical skill extraction
- CTR calculation and recruitment engagement analysis

## Project Structure

```
Recruitment-Data-Analytics-Pipeline/

├── data/
├── src/
│   ├── preprocessing.py
│   ├── feature_extraction.py
│   ├── analysis.py
│   └── pipeline.py
├── notebooks/
├── figures/
├── README.md
└── requirements.txt
```

## Results

The pipeline produces structured recruitment features including:

- Required experience level
- Technical skill demand
- Recruitment engagement metrics

The workflow supports exploratory analysis of recruitment trends and job market patterns.

## Data Availability

This repository is a public portfolio version inspired by real-world recruitment analytics workflows. Synthetic data is used for demonstration while preserving the core data processing methodology.

## Technologies

Python · pandas · NumPy · Matplotlib · Regex · Jupyter
