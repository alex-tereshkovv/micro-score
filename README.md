# MicroScore
*Alternative credit scoring for unbanked populations in Pavlodar region, Kazakhstan*

## Why this matters
In rural Kazakhstan, a large share of adults lack a formal credit history. 
Traditional banks reject them due to missing credit files. 
Microfinance organizations (MFIs) struggle with default prediction using standard methods.

This project tests whether *behavioral banking data* can predict credit risk 
as effectively as traditional credit scores.

The focus is on Pavlodar region, including rural districts: Bayanaul, Uspenka, 
Zhelezinka, Sharbakty, Aktogay, and the city of Pavlodar.

## What the model does
The model predicts whether a person has high or low credit risk based on their 
financial behavior rather than formal credit history.

*Target variable:* credit_risk (0 = low risk, 1 = high risk)

## Data processing
1. Removed non-informative columns: customer_id, loan_default_history, 
   fraud_flag, credit_score
2. One-hot encoding for categorical variables
3. Feature scaling using StandardScaler

## Model
*Logistic Regression* with max_iter=2000

## Results

| Metric | Value |
|--------|-------|
| Accuracy | 0.75 |
| ROC-AUC | 0.83 |

## Feature importance (top predictors)
Positive coefficient = higher credit risk. Negative coefficient = lower risk.

| Feature | Coefficient |
|---------|-------------|
| loan_int_rate | 0.42 |
| person_income | -0.38 |
| loan_percent_income | 0.31 |
| person_emp_length | -0.19 |
| cb_person_default_on_file_Yes | 0.15 |

Note: Exact coefficients may vary slightly depending on dataset version.

## Limitations
- Dataset is synthetic. Next step: pilot with a local MFI in Pavlodar.
- Features like credit_score were removed to test pure behavioral approach.
- Model does not use social graph data due to privacy constraints.

## Next steps (3 months)
1. Reach out to 2-3 microfinance organizations in Pavlodar region
2. Test model on anonymized client data from one local MFI
3. Compare Logistic Regression with Random Forest
4. Identify which features matter most for rural vs urban borrowers
5. Build a simple dashboard for loan officers

## Project structure
MicroScore/
├── data/
│   └── credit_risk_dataset.csv
├── notebooks/
│   └── first_analysis.ipynb
├── .gitignore
├── README.md
└── requirements.txt

## Reproduction

```bash
git clone https://github.com/yourusername/MicroScore.git
cd MicroScore
pip install -r requirements.txt
jupyter notebook notebooks/first_analysis.ipynb

## Code
See first_analysis.ipynb for the complete analysis.

## Author

Alexandr
Pavlodar, Kazakhstan

This project started from a simple observation: people in my region get rejected 
for loans simply because they have no credit history. I am building MicroScore to test 
whether behavioral data could help.