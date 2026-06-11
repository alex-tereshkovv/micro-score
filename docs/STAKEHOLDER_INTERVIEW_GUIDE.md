# MicroScore Stakeholder Interview Guide

This guide helps collect early qualitative feedback from people in Pavlodar and
Pavlodar region. It is for research validation only. It should not collect
sensitive personal data, credit histories, account details, passwords, precise
addresses, phone numbers, or identity documents.

## Goal

MicroScore needs real local feedback to test whether the project is solving the
right problem. The interviews should answer four questions:

1. Do thin-file borrowers in the region actually face the access problem the
   project describes?
2. Which behavioral or financial signals feel fair, explainable, and useful?
3. Which signals feel invasive, unsafe, or likely to exclude people unfairly?
4. What would an MFI analyst need before trusting a model-assisted review tool?

## Consent Script

Use a simple, spoken consent statement before each interview:

```text
I am working on a student research prototype about alternative credit scoring
and financial inclusion in Pavlodar region. This is not a real loan application
and I will not ask for account numbers, passwords, ID documents, precise
addresses, or private financial records. I only want general feedback about
credit access, fairness, and what kind of information would feel acceptable or
unacceptable to use. You can skip any question or stop at any time.
```

Record only summarized notes. Do not record audio or video unless the person
explicitly agrees and there is a clear reason.

## Do Not Collect

- full names;
- phone numbers or private contacts;
- ID numbers;
- exact addresses;
- bank account numbers;
- passwords or login details;
- screenshots of banking apps;
- loan contract documents;
- medical, religious, ethnic, political, or family-member data;
- precise GPS traces;
- anything the person would not want stored in a student research folder.

## Borrower Interview Questions

Start with broad, non-sensitive questions:

1. Have you or people you know had difficulty getting a small loan?
2. What were the main reasons for rejection or uncertainty?
3. Is lack of credit history a real issue in your community?
4. How common is informal or self-employment income?
5. Would a smaller starter loan feel useful if the rules were transparent?

Then ask about fairness and data:

6. Which information would feel fair for an MFI to consider?
7. Which information would feel too private or unsafe?
8. Would mobile-banking activity be acceptable if it were aggregated?
9. Would location at district level feel acceptable?
10. Would late-payment history be fair if the model also considered context?

Then ask about product experience:

11. Would you want to see why a score was high or low?
12. Would you want a manual review or appeal option?
13. What should the system never do automatically?
14. What would make you trust or distrust this kind of tool?
15. What is one thing the project is missing?

## MFI Or Financial Expert Questions

1. What signals do loan officers trust when a borrower has limited credit
   history?
2. Which borrower behaviors are genuinely predictive, and which are misleading?
3. How should late payments be interpreted?
4. What explanations would help an analyst review a score?
5. Which explanations would be useless or dangerous?
6. When should a model recommendation be overridden?
7. Which groups are most at risk of being unfairly rejected?
8. Would a three-zone policy approve/review/decline workflow be useful?
9. What portfolio analytics would matter to an MFI manager?
10. What would be required before using this with real customers?

## Privacy Or Ethics Reviewer Questions

1. Which proposed data categories create the largest privacy risk?
2. Which features should never be used for scoring?
3. Is district-level regional context acceptable, or could it become unfair?
4. How should consent be shown to borrowers?
5. What would a safe pilot data agreement need to include?
6. How should the project communicate synthetic-data limitations?
7. What human oversight should be mandatory?

## Note-Taking Template

Use `data/validation/stakeholder_feedback_template.csv` or the same columns in a
spreadsheet:

- `interview_id`
- `date`
- `stakeholder_type`
- `location_context`
- `topic`
- `observation`
- `project_implication`
- `evidence_status`
- `follow_up`
- `contains_personal_data`

Keep notes short and paraphrased. Use `contains_personal_data = no` for every
row that goes into the project repository.

## Coding Themes

After interviews, tag observations using these themes:

- credit-access barrier;
- thin-file borrower;
- informal income;
- digital access;
- privacy concern;
- fairness concern;
- explanation need;
- manual review need;
- regional assumption;
- MFI workflow;
- product usability;
- pilot-data requirement.

## Minimum Useful Batch

A first validation batch can be small:

- 3 borrower interviews;
- 1 person with lending, finance, or fintech experience;
- 1 privacy/ethics or data-aware reviewer.

The goal is not statistical proof. The goal is to make the project less
abstract and show that the research direction responds to real local feedback.
