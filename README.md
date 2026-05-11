# MicroScore

Alternative credit scoring model for financial inclusion in Kazakhstan.

---

## About this project

This project explores how machine learning can be used to estimate credit risk for people who do not have a traditional credit history. The focus is on behavioral banking data rather than formal financial records.

The idea is especially relevant for regions like Kazakhstan, where many people may not have access to full banking services or stable credit histories.

---

## What the model does

The model predicts whether a person is likely to have a high or low credit risk based on their financial and behavioral activity.

Target variable:
- `credit_risk` (0 = low risk, 1 = high risk)

---

## Data

The dataset includes:
- basic demographic information
- banking activity (deposits, withdrawals, transfers)
- account behavior (logins, usage frequency)
- financial indicators (income, debt, credit score)
- risk-related signals (late payments, fraud flag, loan history)

---

## Approach

1. Data cleaning
   - removed ID columns
   - encoded categorical features

2. Preprocessing
   - scaled numerical features

3. Model
   - Logistic Regression baseline

4. Evaluation
   - Accuracy
   - ROC-AUC

---

## Results

- Accuracy: ~0.75  
- ROC-AUC: ~0.83  

The model shows that behavioral data contains useful signal for predicting credit risk, even without deep financial history.

---

## Structure
MicroScore/
├── notebooks/
│ ├── data/
│ └── first_analysis.ipynb
├── src/
├── .gitignore
├── README.md
├── requirements.txt

---

## What I want to improve next

- try stronger models (Random Forest, Gradient Boosting)
- understand which features matter most
- make results easier to explain
- build a simple interface for predictions

---

## Notes

This is an educational project focused on exploring credit risk modeling and financial inclusion ideas, not a production system.

---

## Author

Built as part of a project exploring how machine learning can be used for credit risk prediction using behavioral data.