# Reflection: Kitewing Help Assistant

Both saved runs use the same local setup (llama3.1:8b for answers and for judging, chunk size 400, hybrid search with re-ranking, confidence threshold -6.9) on the 17 test questions.

## 1. The experiment

I changed one setting: `TOP_K`, the number of chunks sent to the model, from 4 to 2. My hypothesis was that the extra chunks, some scoring -8 to -9, distract the model.

| | TOP_K = 4 (final) | TOP_K = 2 |
|---|---|---|
| Precision@k | 0.32 | 0.57 |
| Recall@k | 1.00 | 0.93 |
| MRR | 0.96 | 0.96 |
| Faithfulness / relevance / completeness (1 to 5) | 5.00 / 5.00 / 5.00 | 4.93 / 4.93 / 4.71 |
| Questions passed | 16 of 17 | 15 of 17 |

Precision improved, but answers got worse. The loss came from the two questions that need two sources: Q11 (the meal limit with archived documents included) and Q17 (annual leave in the US and the UK). With only two chunks, the second source fell out (recall 0.50 on both). The Q11 answer then gave the old $50 limit and told the user to ask Finance for the current one. I kept `TOP_K=4`: precision is not the bottleneck here, and answers that combine versions or regions need room for every source.

## 2. What the chatbot still gets wrong, and why

In the final run, Q11 is the only failure. Retrieval was correct (recall 1.00: both the 2023 and 2025 policy chunks were retrieved) and chunking was not the problem, so the cause is in the prompt and generation stage. The answer opens with the archived $50 limit and only says at the end that it is an older version, which is confusing even though the final statement is right. A clearer conflict instruction in the prompt, such as "state the current limit first, then mention the old one", is the likely fix. A smaller retrieval weakness is Q10, where the correct chunk ranks second (MRR 0.50), but the answer is still right.

## 3. Where the judge disagreed with me

- **Q11 (final run):** the judge labelled the behaviour `corrected_premise`, although the question has no false premise. Its own explanation says the chatbot "correctly identified the current daily meal limit as $75" and mentioned the older version, which describes an ordinary answer. That one label is what failed the question.
- **Q09, across the two runs:** both answers open with "we do not have unlimited vacation" and give the real 20 days, yet one was labelled `corrected_premise` and the other `answered`.
- **Leniency:** the judge gave all 14 judged answers 5/5/5 in the final run. In the TOP_K=2 run it scored Q11 at 4/4/3 even though its own explanation says the answer failed to mention the current limit.

The judge is the same 8b model that wrote the answers, which probably makes it generous, and its labels are not always consistent with its own explanations. So I read every flagged answer myself, and I treat the scores as a way to compare runs, not as absolute quality. A different and stronger judge model would be a better choice.

## 4. How I chose the confidence threshold

I did not guess it. `python generate.py --calibrate` prints the best re-ranker score for every test question. The three questions that should be declined scored -11.0 (World Cup), -10.3 (Director salary as an employee) and -8.6 (dental copay). The lowest answerable question scored -5.15 (the false-premise question, which must be answered so the premise can be corrected). I set the threshold at the midpoint of that gap, -6.9. In both runs the three decline questions were refused without calling the model, and no answerable question was refused. The caveat is that the gap is 3.4 points wide and based on only 17 questions, so I would re-check it whenever the documents change.
