import matplotlib.pyplot as plt
from pathlib import Path

def calculate_ctr(df):
    df = df.copy()
    df["ctr"] = df["clicks"] / df["views"]
    return df

def plot_skill_frequency(df, output):
    skills = df["skills"].explode().value_counts()
    skills.plot(kind="bar")
    plt.title("Top Required Skills")
    plt.tight_layout()
    Path(output).parent.mkdir(exist_ok=True)
    plt.savefig(output)
    plt.close()

def plot_experience_distribution(df, output):
    df["experience_level"].value_counts().plot(kind="bar")
    plt.title("Experience Requirement Distribution")
    plt.tight_layout()
    Path(output).parent.mkdir(exist_ok=True)
    plt.savefig(output)
    plt.close()

def plot_ctr_analysis(df, output):
    df.groupby("job_title")["ctr"].mean().plot(kind="bar")
    plt.title("Average CTR by Job Title")
    plt.tight_layout()
    Path(output).parent.mkdir(exist_ok=True)
    plt.savefig(output)
    plt.close()
