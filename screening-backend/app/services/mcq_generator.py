# app/services/mcq_generator.py

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import List, Literal, Sequence

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, conlist


class MCQOption(BaseModel):
    key: Literal["A", "B", "C", "D"]
    text: str


class MCQItem(BaseModel):
    question_text: str
    options: conlist(MCQOption, min_length=4, max_length=4)
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str
    difficulty_level: Literal["easy", "medium", "hard"] = "medium"


class MCQTestBundle(BaseModel):
    questions: conlist(MCQItem, min_length=30, max_length=30)


@dataclass(frozen=True)
class _RawMCQ:
    question_text: str
    options: List[tuple[str, str]]
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str
    difficulty_level: Literal["easy", "medium", "hard"] = "medium"


class MCQGenerator:
    """
    Generates a 30-question MCQ test.

    Primary path:
        OpenAI structured output via LangChain

    Fallback path:
        Curated role-specific question banks + generic expansion + adaptive fillers
    """

    def __init__(
        self,
        model_name: str | None = None,
        temperature: float = 0.7,
    ) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = temperature

        self.llm = None
        self.chain = None

        if api_key:
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
            )

            self.prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        (
                            "You are a senior technical assessment designer.\n"
                            "Generate a completely fresh, unique MCQ test for one candidate only.\n"
                            "Do NOT use any static question bank.\n"
                            "Do NOT repeat questions.\n"
                            "Do NOT output anything outside the requested schema.\n"
                            "Each question must have exactly 4 options labeled A, B, C, D.\n"
                            "Each question must have exactly one correct answer.\n"
                            "Avoid vague wording, avoid duplicate stems, avoid 'all of the above' and 'none of the above'.\n"
                            "Make the test strongly personalized to the candidate's role and extracted profile.\n"
                            "Vary difficulty based on experience: easier for juniors, deeper for experienced candidates.\n"
                            "Use a mix of conceptual, practical, and scenario-based questions."
                        ),
                    ),
                    (
                        "user",
                        (
                            "Target role: {role_name}\n"
                            "Candidate extracted profile:\n"
                            "- Skills: {skills}\n"
                            "- Technologies: {technologies}\n"
                            "- Years of experience: {years_of_experience}\n\n"
                            "Generate exactly 30 unique MCQs for this candidate.\n"
                            "The test must be personalized to this role and this profile.\n"
                            "Return the answer key internally in the structured output."
                        ),
                    ),
                ]
            )

            self.structured_llm = self.llm.with_structured_output(
                MCQTestBundle,
                method="json_schema",
            )

            self.chain = self.prompt | self.structured_llm

    def generate_test(self, role_name: str, extracted_profile: dict) -> dict:
        """
        Try OpenAI first. If it fails or returns invalid structure, use the fallback bank.
        """
        skills = extracted_profile.get("skills", []) or []
        technologies = extracted_profile.get("technologies", []) or []
        years = extracted_profile.get("years_of_experience", 0.0) or 0.0

        if self.chain is not None:
            try:
                result: MCQTestBundle = self.chain.invoke(
                    {
                        "role_name": role_name,
                        "skills": ", ".join(skills) if skills else "none",
                        "technologies": ", ".join(technologies) if technologies else "none",
                        "years_of_experience": years,
                    }
                )
                payload = result.model_dump()
                if len(payload.get("questions", [])) == 30:
                    return payload
            except Exception:
                pass

        return self._fallback_generate(role_name, extracted_profile)

    def _fallback_generate(self, role_name: str, extracted_profile: dict) -> dict:
        """
        Robust fallback that constructs a full 30-question test from:
        1) role-specific pools
        2) expanded generic pool
        3) adaptive fillers if still short
        """
        role_key = self._normalize_role(role_name)
        skills = extracted_profile.get("skills", []) or []
        technologies = extracted_profile.get("technologies", []) or []
        years = float(extracted_profile.get("years_of_experience", 0.0) or 0.0)

        pool = self._build_pool(role_key, skills, technologies, years)

        seed_source = f"{role_name}|{','.join(skills)}|{','.join(technologies)}|{years}"
        offset = self._stable_offset(seed_source, len(pool))
        ordered = pool[offset:] + pool[:offset]

        selected: List[_RawMCQ] = []
        seen_texts = set()

        for item in ordered:
            if item.question_text not in seen_texts:
                selected.append(item)
                seen_texts.add(item.question_text)
            if len(selected) >= 30:
                break

        # If still short, use a larger generic pool to fill.
        if len(selected) < 30:
            generic_pool = self._generic_pool()
            generic_offset = self._stable_offset(seed_source[::-1], len(generic_pool))
            generic_ordered = generic_pool[generic_offset:] + generic_pool[:generic_offset]

            for item in generic_ordered:
                if item.question_text not in seen_texts:
                    selected.append(item)
                    seen_texts.add(item.question_text)
                if len(selected) >= 30:
                    break

        # Final safety net: adaptive fillers generated from profile context.
        if len(selected) < 30:
            for item in self._adaptive_fillers(role_name, skills, technologies, years):
                if item.question_text not in seen_texts:
                    selected.append(item)
                    seen_texts.add(item.question_text)
                if len(selected) >= 30:
                    break

        # Last safety net in case of unexpected future edits to pools.
        if len(selected) < 30:
            while len(selected) < 30:
                filler = self._last_resort_filler(role_name, skills, technologies, years, len(selected) + 1)
                if filler.question_text not in seen_texts:
                    selected.append(filler)
                    seen_texts.add(filler.question_text)

        selected = selected[:30]
        questions = [self._to_mcq_item(raw).model_dump() for raw in selected]

        # Validate at the boundary so any bug is visible immediately during dev.
        return MCQTestBundle(questions=questions).model_dump()

    def _build_pool(
        self,
        role_key: str,
        skills: Sequence[str],
        technologies: Sequence[str],
        years: float,
    ) -> List[_RawMCQ]:
        role_pools = {
            "ai_ml_engineer": self._ai_ml_pool(),
            "data_scientist": self._data_scientist_pool(),
            "backend_engineer": self._backend_pool(),
        }

        pool = list(role_pools.get(role_key, self._generic_pool()))

        # Personalized inserts improve perceived uniqueness.
        if any("python" in t.lower() for t in technologies):
            pool.insert(
                0,
                _RawMCQ(
                    question_text="In a Python-based ML pipeline, which approach most directly helps prevent data leakage during preprocessing?",
                    options=[
                        ("A", "Fit transformers on the entire dataset before splitting"),
                        ("B", "Split the dataset first, then fit preprocessing only on the training set"),
                        ("C", "Encode labels after evaluating the model"),
                        ("D", "Normalize the test set separately before training"),
                    ],
                    correct_answer="B",
                    explanation="Preprocessing must be fit on the training set only to avoid leakage into validation/test data.",
                    difficulty_level="medium",
                ),
            )

        if years >= 2.0:
            pool.insert(
                0,
                _RawMCQ(
                    question_text="A candidate with some project experience wants to choose between a simple baseline model and a more complex model. What is the most defensible first step?",
                    options=[
                        ("A", "Choose the most complex model to maximize accuracy immediately"),
                        ("B", "Establish a simple baseline and compare it against stronger candidates"),
                        ("C", "Skip baselines because they are outdated"),
                        ("D", "Always use ensemble methods regardless of data size"),
                    ],
                    correct_answer="B",
                    explanation="Baselines provide a reference point and justify complexity only when it adds measurable value.",
                    difficulty_level="easy",
                ),
            )

        deduped: List[_RawMCQ] = []
        seen = set()
        for item in pool:
            if item.question_text not in seen:
                deduped.append(item)
                seen.add(item.question_text)

        return deduped

    def _ai_ml_pool(self) -> List[_RawMCQ]:
        return [
            _RawMCQ(
                question_text="Which metric is most appropriate when false negatives are especially costly in a binary classification task?",
                options=[
                    ("A", "Accuracy"),
                    ("B", "Precision"),
                    ("C", "Recall"),
                    ("D", "R-squared"),
                ],
                correct_answer="C",
                explanation="Recall measures how many actual positives are correctly identified, which matters when missing positives is costly.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main purpose of regularization in machine learning models?",
                options=[
                    ("A", "Increase training speed only"),
                    ("B", "Reduce overfitting by penalizing excessive complexity"),
                    ("C", "Convert supervised learning into unsupervised learning"),
                    ("D", "Increase the number of labels in the dataset"),
                ],
                correct_answer="B",
                explanation="Regularization reduces overfitting by controlling model complexity.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is a validation set used during model development?",
                options=[
                    ("A", "To train the model faster"),
                    ("B", "To tune hyperparameters and compare models without touching the test set"),
                    ("C", "To replace the need for training data"),
                    ("D", "To increase the number of features available to the model"),
                ],
                correct_answer="B",
                explanation="The validation set is used for model selection and tuning while preserving the test set for final evaluation.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="In gradient descent, what does the learning rate control?",
                options=[
                    ("A", "The number of features used by the model"),
                    ("B", "The step size taken in the direction of the gradient"),
                    ("C", "The size of the training set"),
                    ("D", "The number of hidden layers in a neural network"),
                ],
                correct_answer="B",
                explanation="The learning rate controls the size of each update step during optimization.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which situation most strongly suggests overfitting?",
                options=[
                    ("A", "High training accuracy and much lower validation accuracy"),
                    ("B", "Low training accuracy and low validation accuracy"),
                    ("C", "Training and validation accuracy both high and similar"),
                    ("D", "Validation accuracy slightly higher than training accuracy"),
                ],
                correct_answer="A",
                explanation="A large gap between training and validation performance is a classic overfitting signal.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does the bias-variance tradeoff describe?",
                options=[
                    ("A", "The relationship between training time and hardware cost"),
                    ("B", "The balance between underfitting and overfitting sources of error"),
                    ("C", "The tradeoff between classification and regression tasks only"),
                    ("D", "The relationship between data size and batch size"),
                ],
                correct_answer="B",
                explanation="Bias and variance are two major sources of generalization error, and model choice balances them.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why is cross-validation useful?",
                options=[
                    ("A", "It removes the need for a test set"),
                    ("B", "It provides a more stable estimate of generalization performance"),
                    ("C", "It guarantees zero overfitting"),
                    ("D", "It doubles the size of the dataset"),
                ],
                correct_answer="B",
                explanation="Cross-validation reduces dependence on a single split and gives a more robust estimate.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="In a neural network, what is the role of an activation function?",
                options=[
                    ("A", "It converts the model into a decision tree"),
                    ("B", "It introduces non-linearity so the network can model complex patterns"),
                    ("C", "It removes the need for training data"),
                    ("D", "It directly normalizes the output labels"),
                ],
                correct_answer="B",
                explanation="Without non-linear activations, stacked layers collapse into a linear transformation.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Which of the following is a common reason to use early stopping?",
                options=[
                    ("A", "To increase the number of classes"),
                    ("B", "To avoid overfitting when validation performance stops improving"),
                    ("C", "To make the loss function non-differentiable"),
                    ("D", "To reduce the number of features in the dataset"),
                ],
                correct_answer="B",
                explanation="Early stopping halts training when validation metrics plateau or degrade.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the key difference between bagging and boosting?",
                options=[
                    ("A", "Bagging trains models sequentially, boosting trains them independently"),
                    ("B", "Bagging reduces variance by averaging independent models; boosting focuses sequentially on difficult cases"),
                    ("C", "Bagging only works for regression, boosting only for classification"),
                    ("D", "They are identical ensemble methods"),
                ],
                correct_answer="B",
                explanation="Bagging is parallel and variance-reducing; boosting is sequential and often reduces bias.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="When should F1-score be preferred over accuracy?",
                options=[
                    ("A", "When classes are imbalanced and both precision and recall matter"),
                    ("B", "When the target is continuous"),
                    ("C", "When there is no positive class"),
                    ("D", "When the dataset has no missing values"),
                ],
                correct_answer="A",
                explanation="F1-score balances precision and recall and is more informative for imbalanced classification.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is concept drift in production ML systems?",
                options=[
                    ("A", "A GPU memory issue during training"),
                    ("B", "When the relationship between features and target changes over time"),
                    ("C", "A type of regularization penalty"),
                    ("D", "The process of compressing models for deployment"),
                ],
                correct_answer="B",
                explanation="Concept drift occurs when the underlying data distribution or target relationship changes.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why might a transformer outperform an RNN on long sequences?",
                options=[
                    ("A", "Transformers cannot process long sequences"),
                    ("B", "Self-attention can model long-range dependencies more directly"),
                    ("C", "Transformers always use fewer parameters than RNNs"),
                    ("D", "RNNs are only useful for images"),
                ],
                correct_answer="B",
                explanation="Self-attention enables direct interaction across sequence positions, helping with long-range dependencies.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="In feature engineering, why is one-hot encoding used for categorical variables?",
                options=[
                    ("A", "To turn categories into ordered numeric rankings"),
                    ("B", "To represent categories without introducing a false ordinal relationship"),
                    ("C", "To reduce the number of classes to one"),
                    ("D", "To increase the target variable values"),
                ],
                correct_answer="B",
                explanation="One-hot encoding avoids implying an artificial order among categories.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is a principal advantage of ROC-AUC?",
                options=[
                    ("A", "It only works for regression"),
                    ("B", "It summarizes ranking performance across thresholds"),
                    ("C", "It measures exact probability calibration only"),
                    ("D", "It is identical to accuracy"),
                ],
                correct_answer="B",
                explanation="ROC-AUC evaluates ranking quality across all classification thresholds.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What does batch normalization primarily help with during neural network training?",
                options=[
                    ("A", "It removes the need for labels"),
                    ("B", "It stabilizes and speeds up training by normalizing layer inputs"),
                    ("C", "It converts classification into regression"),
                    ("D", "It replaces activation functions entirely"),
                ],
                correct_answer="B",
                explanation="Batch normalization can improve training stability and convergence speed.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Which statement best describes transfer learning?",
                options=[
                    ("A", "Training a model from scratch on every new dataset"),
                    ("B", "Reusing knowledge from a pretrained model for a related task"),
                    ("C", "Removing all pretrained weights before inference"),
                    ("D", "Using random labels to initialize a model"),
                ],
                correct_answer="B",
                explanation="Transfer learning adapts pretrained representations to a new task.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the practical reason to monitor model confidence after deployment?",
                options=[
                    ("A", "To make the UI colorful"),
                    ("B", "To detect unusual predictions or drifting data patterns"),
                    ("C", "To remove the need for retraining"),
                    ("D", "To improve SQL indexing"),
                ],
                correct_answer="B",
                explanation="Monitoring confidence can help identify drift, uncertainty, or suspicious behavior.",
                difficulty_level="hard",
            ),
            _RawMCQ(
                question_text="Why can class imbalance make accuracy misleading?",
                options=[
                    ("A", "Because accuracy is undefined for classification"),
                    ("B", "Because a model can predict the majority class and still score highly"),
                    ("C", "Because imbalance always prevents training"),
                    ("D", "Because accuracy only works for balanced datasets"),
                ],
                correct_answer="B",
                explanation="A majority-class predictor can appear strong on accuracy while failing minority classes.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="When tuning hyperparameters, what is the safest set to keep untouched until the end?",
                options=[
                    ("A", "Training set"),
                    ("B", "Validation set"),
                    ("C", "Test set"),
                    ("D", "Feature set"),
                ],
                correct_answer="C",
                explanation="The test set should be reserved for final unbiased evaluation.",
                difficulty_level="easy",
            ),
        ]

    def _data_scientist_pool(self) -> List[_RawMCQ]:
        return [
            _RawMCQ(
                question_text="What is the main advantage of using a train-validation-test split?",
                options=[
                    ("A", "It ensures the model memorizes the data"),
                    ("B", "It separates training, tuning, and final evaluation responsibilities"),
                    ("C", "It guarantees the best possible score"),
                    ("D", "It removes the need for labels"),
                ],
                correct_answer="B",
                explanation="Separating the splits avoids contaminating the final evaluation set.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which chart is most suitable for visualizing the distribution of a single continuous variable?",
                options=[
                    ("A", "Histogram"),
                    ("B", "Pie chart"),
                    ("C", "Heatmap"),
                    ("D", "Stacked area chart"),
                ],
                correct_answer="A",
                explanation="Histograms are standard for inspecting the distribution of continuous data.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is missing value handling important before modeling?",
                options=[
                    ("A", "Because all models can handle missing values automatically"),
                    ("B", "Because missingness can break algorithms or bias results if ignored"),
                    ("C", "Because it always improves accuracy by itself"),
                    ("D", "Because it changes the target variable into features"),
                ],
                correct_answer="B",
                explanation="Missing data can distort patterns or cause training failures depending on the model.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the purpose of an outlier analysis step in data preprocessing?",
                options=[
                    ("A", "To create additional labels"),
                    ("B", "To identify extreme values that may distort statistics or model behavior"),
                    ("C", "To make all data categorical"),
                    ("D", "To eliminate the need for scaling"),
                ],
                correct_answer="B",
                explanation="Outliers can heavily influence means, variance, and many algorithms.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which metric is most informative for an imbalanced binary classification problem?",
                options=[
                    ("A", "Accuracy only"),
                    ("B", "Precision, recall, and F1-score"),
                    ("C", "Mean squared error"),
                    ("D", "R-squared"),
                ],
                correct_answer="B",
                explanation="Accuracy can be misleading on imbalanced classes; precision/recall/F1 are better.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does a p-value help assess in hypothesis testing?",
                options=[
                    ("A", "The exact probability that the null hypothesis is true"),
                    ("B", "How surprising the observed result is under the null hypothesis"),
                    ("C", "The size of the dataset"),
                    ("D", "The model’s prediction confidence"),
                ],
                correct_answer="B",
                explanation="A p-value measures how extreme the observed data is if the null hypothesis were true.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why might a data scientist prefer stratified sampling?",
                options=[
                    ("A", "To remove all variance from the dataset"),
                    ("B", "To preserve class proportions across splits"),
                    ("C", "To increase feature dimensionality"),
                    ("D", "To convert regression into classification"),
                ],
                correct_answer="B",
                explanation="Stratification keeps the class distribution similar in train/test splits.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is multicollinearity in linear models?",
                options=[
                    ("A", "A type of clustering algorithm"),
                    ("B", "High correlation among predictor variables"),
                    ("C", "A method for imputing missing values"),
                    ("D", "A form of cross-validation"),
                ],
                correct_answer="B",
                explanation="Multicollinearity means predictors are strongly correlated, which can destabilize coefficient estimates.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why do we scale features before using distance-based algorithms like k-NN?",
                options=[
                    ("A", "To make target labels categorical"),
                    ("B", "To ensure features with larger numeric ranges do not dominate distances"),
                    ("C", "To remove all outliers automatically"),
                    ("D", "To increase class imbalance"),
                ],
                correct_answer="B",
                explanation="Distance-based methods are sensitive to feature scale.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does A/B testing primarily help determine?",
                options=[
                    ("A", "Which feature engineering method is mathematically optimal"),
                    ("B", "Whether a change causes a measurable difference in user or business outcome"),
                    ("C", "How many rows should be deleted from the dataset"),
                    ("D", "Whether the model can overfit faster"),
                ],
                correct_answer="B",
                explanation="A/B testing compares variants under controlled conditions to estimate impact.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the main benefit of feature selection?",
                options=[
                    ("A", "It always increases the number of classes"),
                    ("B", "It can reduce noise, overfitting, and model complexity"),
                    ("C", "It guarantees perfect prediction"),
                    ("D", "It removes the need for validation"),
                ],
                correct_answer="B",
                explanation="Good feature selection can improve interpretability and generalization.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Which method is most appropriate for evaluating a regression model?",
                options=[
                    ("A", "Mean Absolute Error (MAE)"),
                    ("B", "Accuracy"),
                    ("C", "Precision"),
                    ("D", "Confusion matrix"),
                ],
                correct_answer="A",
                explanation="MAE is a standard regression metric based on prediction error magnitude.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does bootstrapping help estimate?",
                options=[
                    ("A", "The exact architecture of a neural network"),
                    ("B", "Sampling variability and confidence intervals from repeated resampling"),
                    ("C", "The number of hidden classes in a dataset"),
                    ("D", "The learning rate schedule of gradient descent"),
                ],
                correct_answer="B",
                explanation="Bootstrapping repeatedly resamples data to estimate uncertainty and variability.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why is log transformation sometimes applied to skewed data?",
                options=[
                    ("A", "To increase skewness"),
                    ("B", "To compress large values and make distributions more symmetric"),
                    ("C", "To convert continuous data into labels"),
                    ("D", "To remove the need for scaling completely"),
                ],
                correct_answer="B",
                explanation="Log transforms reduce the effect of extreme values and often stabilize variance.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the most important consideration when deploying a model for business use?",
                options=[
                    ("A", "Only the training score"),
                    ("B", "Performance, interpretability, latency, and monitoring needs"),
                    ("C", "The number of notebooks used during experimentation"),
                    ("D", "The size of the font in the report"),
                ],
                correct_answer="B",
                explanation="Production deployment requires technical and operational tradeoffs beyond raw accuracy.",
                difficulty_level="hard",
            ),
            _RawMCQ(
                question_text="Why is data leakage a major concern in predictive modeling?",
                options=[
                    ("A", "It makes the model slower but more accurate"),
                    ("B", "It inflates evaluation results by exposing future information during training"),
                    ("C", "It only affects unsupervised learning"),
                    ("D", "It is harmless if the dataset is large"),
                ],
                correct_answer="B",
                explanation="Leakage causes overly optimistic performance estimates that fail in the real world.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Which approach is most suitable for tracking a model in production over time?",
                options=[
                    ("A", "Ignore metrics once deployment is complete"),
                    ("B", "Monitor prediction quality, latency, and data drift regularly"),
                    ("C", "Only save the training notebook"),
                    ("D", "Replace logging with manual guesses"),
                ],
                correct_answer="B",
                explanation="Production monitoring is essential for reliability and early drift detection.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the role of a confusion matrix?",
                options=[
                    ("A", "To visualize the feature importance only"),
                    ("B", "To summarize classification outcomes by true and predicted labels"),
                    ("C", "To calculate regression error directly"),
                    ("D", "To replace cross-validation"),
                ],
                correct_answer="B",
                explanation="A confusion matrix breaks down true positives, false positives, true negatives, and false negatives.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why might you prefer median over mean for a skewed distribution?",
                options=[
                    ("A", "Median is always larger than mean"),
                    ("B", "Median is less sensitive to extreme outliers"),
                    ("C", "Mean cannot be computed"),
                    ("D", "Median is a classification metric"),
                ],
                correct_answer="B",
                explanation="Median is robust to extreme values compared with the mean.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the practical use of clustering in exploratory analysis?",
                options=[
                    ("A", "To assign supervised labels to all data"),
                    ("B", "To uncover natural groupings or segments in unlabeled data"),
                    ("C", "To reduce the need for plotting"),
                    ("D", "To convert time series into text"),
                ],
                correct_answer="B",
                explanation="Clustering helps identify patterns and segments in unlabeled data.",
                difficulty_level="medium",
            ),
        ]

    def _backend_pool(self) -> List[_RawMCQ]:
        return [
            _RawMCQ(
                question_text="What is the primary purpose of an API?",
                options=[
                    ("A", "To store passwords in plain text"),
                    ("B", "To define a contract for communication between software components"),
                    ("C", "To replace a database"),
                    ("D", "To eliminate the need for endpoints"),
                ],
                correct_answer="B",
                explanation="APIs define structured communication between systems.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which HTTP method is typically used to retrieve a resource without changing it?",
                options=[
                    ("A", "POST"),
                    ("B", "GET"),
                    ("C", "PATCH"),
                    ("D", "DELETE"),
                ],
                correct_answer="B",
                explanation="GET is used for read-only retrieval of resources.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main benefit of indexing a database column?",
                options=[
                    ("A", "It always reduces storage costs to zero"),
                    ("B", "It improves lookup performance for queries on that column"),
                    ("C", "It removes the need for SQL"),
                    ("D", "It guarantees no duplicates in the table"),
                ],
                correct_answer="B",
                explanation="Indexes speed up lookups but can add storage and write overhead.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What problem does caching mainly solve?",
                options=[
                    ("A", "It makes databases unnecessary"),
                    ("B", "It reduces repeated computation or retrieval latency"),
                    ("C", "It prevents all bugs"),
                    ("D", "It converts SQL into NoSQL automatically"),
                ],
                correct_answer="B",
                explanation="Caching stores frequently accessed data for quicker access.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="In a REST API, what does statelessness mean?",
                options=[
                    ("A", "The server stores all client session history forever"),
                    ("B", "Each request contains all information needed to process it"),
                    ("C", "The client never sends headers"),
                    ("D", "The API cannot return JSON"),
                ],
                correct_answer="B",
                explanation="Stateless requests do not depend on server-side session memory.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why is pagination used in API responses?",
                options=[
                    ("A", "To increase the size of the payload"),
                    ("B", "To limit the amount of data returned in a single response"),
                    ("C", "To replace authentication"),
                    ("D", "To encrypt the response body"),
                ],
                correct_answer="B",
                explanation="Pagination improves usability and performance when returning large collections.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the key difference between SQL and NoSQL databases?",
                options=[
                    ("A", "SQL databases are always faster in every workload"),
                    ("B", "SQL databases are typically relational and schema-driven, while NoSQL systems offer more flexible data models"),
                    ("C", "NoSQL databases cannot scale horizontally"),
                    ("D", "SQL cannot support transactions"),
                ],
                correct_answer="B",
                explanation="The main difference is data model and schema flexibility, not a universal performance rule.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Which of the following is a common cause of high latency in a backend service?",
                options=[
                    ("A", "Excessive network/database round trips"),
                    ("B", "Using a GET endpoint"),
                    ("C", "Returning JSON instead of XML"),
                    ("D", "Having a README file"),
                ],
                correct_answer="A",
                explanation="Repeated I/O and network calls often increase latency substantially.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the purpose of an ORM?",
                options=[
                    ("A", "To eliminate the need for a database"),
                    ("B", "To map objects in code to database records and simplify persistence logic"),
                    ("C", "To convert Python into JavaScript"),
                    ("D", "To replace HTTP"),
                ],
                correct_answer="B",
                explanation="ORMs help developers work with relational data using higher-level objects.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="When would you prefer asynchronous processing in a backend system?",
                options=[
                    ("A", "When the request needs immediate blocking feedback only"),
                    ("B", "When a task is time-consuming and can be handled without blocking the response"),
                    ("C", "When the system has no users"),
                    ("D", "When the API is read-only"),
                ],
                correct_answer="B",
                explanation="Async/background processing improves responsiveness for long-running tasks.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is a primary reason to use a message queue?",
                options=[
                    ("A", "To make every request synchronous"),
                    ("B", "To decouple producers and consumers and buffer workloads"),
                    ("C", "To remove the need for retries"),
                    ("D", "To store only HTML pages"),
                ],
                correct_answer="B",
                explanation="Queues help separate systems and smooth spikes in traffic.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What does rate limiting protect a service from?",
                options=[
                    ("A", "Underutilization only"),
                    ("B", "Excessive request volume and abuse"),
                    ("C", "Using too many database indexes"),
                    ("D", "Invalid JSON responses"),
                ],
                correct_answer="B",
                explanation="Rate limiting controls traffic to preserve service stability.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main purpose of horizontal scaling?",
                options=[
                    ("A", "To add more CPU to one machine only"),
                    ("B", "To add more machines to distribute load"),
                    ("C", "To reduce code readability"),
                    ("D", "To disable caching"),
                ],
                correct_answer="B",
                explanation="Horizontal scaling adds more instances to share workload.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why are transactions important in relational databases?",
                options=[
                    ("A", "They guarantee the UI is responsive"),
                    ("B", "They provide atomicity and consistency for multi-step updates"),
                    ("C", "They remove the need for indexes"),
                    ("D", "They always increase throughput"),
                ],
                correct_answer="B",
                explanation="Transactions ensure a group of operations succeeds or fails together.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is a common advantage of using FastAPI or similar modern frameworks?",
                options=[
                    ("A", "Automatic HTML design generation"),
                    ("B", "Type hints, validation, and fast API development"),
                    ("C", "They remove the need for route definitions"),
                    ("D", "They eliminate all production monitoring needs"),
                ],
                correct_answer="B",
                explanation="Modern Python frameworks improve developer productivity and validation.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is idempotency important for certain HTTP methods?",
                options=[
                    ("A", "It ensures that repeated requests have the same effect as one request"),
                    ("B", "It makes every request faster"),
                    ("C", "It prevents all server errors"),
                    ("D", "It converts JSON into XML"),
                ],
                correct_answer="A",
                explanation="Idempotency helps make retries safe and predictable.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the purpose of connection pooling in backend systems?",
                options=[
                    ("A", "To make HTTP requests encrypted"),
                    ("B", "To reuse database connections and reduce overhead"),
                    ("C", "To store API secrets in memory only"),
                    ("D", "To eliminate the need for a DB engine"),
                ],
                correct_answer="B",
                explanation="Pooling reduces the cost of repeatedly creating new connections.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is a likely benefit of using background workers for notifications or reports?",
                options=[
                    ("A", "They block the user request until completion"),
                    ("B", "They keep the API responsive while work is processed separately"),
                    ("C", "They remove the need for logging"),
                    ("D", "They disable retries"),
                ],
                correct_answer="B",
                explanation="Background workers offload long-running jobs from the main request path.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What does a timeout prevent in distributed systems?",
                options=[
                    ("A", "Requests waiting forever for a response"),
                    ("B", "Data from being stored in a database"),
                    ("C", "Code from compiling"),
                    ("D", "JSON from being parsed"),
                ],
                correct_answer="A",
                explanation="Timeouts prevent indefinite blocking when a downstream service is unavailable.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main purpose of database normalization?",
                options=[
                    ("A", "Increase duplicated data"),
                    ("B", "Reduce redundancy and improve data integrity"),
                    ("C", "Make all fields nullable"),
                    ("D", "Replace indexes with caching"),
                ],
                correct_answer="B",
                explanation="Normalization structures data to avoid redundancy and update anomalies.",
                difficulty_level="medium",
            ),
        ]

    def _generic_pool(self) -> List[_RawMCQ]:
        # Expanded by more than 15 unique questions as requested.
        return [
            _RawMCQ(
                question_text="What is the primary goal of unit testing?",
                options=[
                    ("A", "To validate a full production deployment"),
                    ("B", "To verify the behavior of a small unit of code in isolation"),
                    ("C", "To replace integration testing entirely"),
                    ("D", "To increase code size"),
                ],
                correct_answer="B",
                explanation="Unit tests focus on individual functions or components.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which algorithmic complexity is generally better for large inputs?",
                options=[
                    ("A", "O(n^2)"),
                    ("B", "O(log n)"),
                    ("C", "O(n^3)"),
                    ("D", "O(2^n)"),
                ],
                correct_answer="B",
                explanation="Lower growth rates scale better as input size increases.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why are data structures important in software engineering?",
                options=[
                    ("A", "They only matter in interviews"),
                    ("B", "They help organize data efficiently for access and modification"),
                    ("C", "They remove the need for algorithms"),
                    ("D", "They are useful only for frontend work"),
                ],
                correct_answer="B",
                explanation="Choosing the right structure can improve performance and clarity.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main benefit of code version control?",
                options=[
                    ("A", "It prevents all bugs automatically"),
                    ("B", "It tracks changes and enables collaboration and rollback"),
                    ("C", "It replaces documentation completely"),
                    ("D", "It removes the need for testing"),
                ],
                correct_answer="B",
                explanation="Version control preserves history and supports teamwork.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does an algorithm typically require to be useful?",
                options=[
                    ("A", "Randomness only"),
                    ("B", "Clear inputs, a deterministic process, and a defined output"),
                    ("C", "A graphical interface"),
                    ("D", "A database connection"),
                ],
                correct_answer="B",
                explanation="Algorithms transform inputs into outputs according to defined steps.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is documentation valuable in engineering teams?",
                options=[
                    ("A", "It replaces code reviews"),
                    ("B", "It helps others understand, maintain, and use the system"),
                    ("C", "It makes deployments slower by design"),
                    ("D", "It only matters for managers"),
                ],
                correct_answer="B",
                explanation="Good documentation improves maintainability and onboarding.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the purpose of debugging?",
                options=[
                    ("A", "To intentionally add more errors"),
                    ("B", "To identify and fix defects in code"),
                    ("C", "To reduce team communication"),
                    ("D", "To replace compilation"),
                ],
                correct_answer="B",
                explanation="Debugging is the process of locating and correcting defects.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is a stack data structure best characterized by?",
                options=[
                    ("A", "FIFO"),
                    ("B", "LIFO"),
                    ("C", "Random access"),
                    ("D", "Sorted order only"),
                ],
                correct_answer="B",
                explanation="Stacks follow last-in, first-out behavior.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is a queue data structure best characterized by?",
                options=[
                    ("A", "LIFO"),
                    ("B", "FIFO"),
                    ("C", "No ordering"),
                    ("D", "Tree traversal only"),
                ],
                correct_answer="B",
                explanation="Queues follow first-in, first-out behavior.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why do software systems use abstractions?",
                options=[
                    ("A", "To hide all functionality from users"),
                    ("B", "To manage complexity by exposing only essential details"),
                    ("C", "To eliminate edge cases"),
                    ("D", "To increase coupling"),
                ],
                correct_answer="B",
                explanation="Abstraction simplifies interaction with complex internals.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the role of error handling in an application?",
                options=[
                    ("A", "To hide issues permanently"),
                    ("B", "To handle unexpected conditions gracefully and safely"),
                    ("C", "To replace logging"),
                    ("D", "To make code longer by default"),
                ],
                correct_answer="B",
                explanation="Robust error handling improves reliability and user experience.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is modular code generally preferred?",
                options=[
                    ("A", "It always runs without bugs"),
                    ("B", "It is easier to maintain, test, and reuse"),
                    ("C", "It reduces the need for collaboration"),
                    ("D", "It eliminates documentation needs"),
                ],
                correct_answer="B",
                explanation="Smaller, well-defined modules improve maintainability.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main purpose of logging in software systems?",
                options=[
                    ("A", "To make the application slower"),
                    ("B", "To record useful runtime information for debugging and monitoring"),
                    ("C", "To replace automated tests"),
                    ("D", "To avoid code reviews"),
                ],
                correct_answer="B",
                explanation="Logs help trace runtime behavior and diagnose failures.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Which concept best describes a reusable software component?",
                options=[
                    ("A", "Tight coupling"),
                    ("B", "Encapsulation"),
                    ("C", "Monolithic design only"),
                    ("D", "Dead code"),
                ],
                correct_answer="B",
                explanation="Encapsulation helps build reusable and maintainable components.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What does API authentication verify?",
                options=[
                    ("A", "That the user is allowed to see the data after access is granted"),
                    ("B", "That the caller is who they claim to be"),
                    ("C", "That the database is normalized"),
                    ("D", "That the UI is responsive"),
                ],
                correct_answer="B",
                explanation="Authentication verifies identity; authorization controls access rights.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the purpose of authorization?",
                options=[
                    ("A", "To verify identity"),
                    ("B", "To determine what an authenticated user is allowed to do"),
                    ("C", "To compress JSON data"),
                    ("D", "To build user interfaces"),
                ],
                correct_answer="B",
                explanation="Authorization decides permitted actions after identity is known.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why do distributed systems need retries?",
                options=[
                    ("A", "Because all failures are permanent"),
                    ("B", "Because transient failures can be resolved by repeating the operation"),
                    ("C", "Because retries always improve correctness"),
                    ("D", "Because they replace logging"),
                ],
                correct_answer="B",
                explanation="Retries are useful for temporary network or dependency issues.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What is the purpose of an interface in object-oriented design?",
                options=[
                    ("A", "To define a contract that implementation classes follow"),
                    ("B", "To store binary files"),
                    ("C", "To replace inheritance entirely"),
                    ("D", "To make code untestable"),
                ],
                correct_answer="A",
                explanation="Interfaces define behavior without committing to implementation details.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="What should you prioritize when designing maintainable code?",
                options=[
                    ("A", "Maximum line count"),
                    ("B", "Readability, testability, and clear boundaries"),
                    ("C", "Avoiding comments always"),
                    ("D", "Using the most complex pattern possible"),
                ],
                correct_answer="B",
                explanation="Maintainable code is easy to understand, test, and evolve.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main reason to avoid hardcoded configuration values?",
                options=[
                    ("A", "They make applications impossible to deploy"),
                    ("B", "They reduce flexibility and make environment changes harder"),
                    ("C", "They always slow down the CPU"),
                    ("D", "They stop version control from working"),
                ],
                correct_answer="B",
                explanation="Configuration should be externalized for portability and maintainability.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="Why is input validation important at system boundaries?",
                options=[
                    ("A", "To make code shorter"),
                    ("B", "To prevent invalid data from causing failures or security issues"),
                    ("C", "To improve font rendering"),
                    ("D", "To eliminate the need for exceptions"),
                ],
                correct_answer="B",
                explanation="Validation protects stability and security by rejecting bad inputs early.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is the main purpose of a smoke test?",
                options=[
                    ("A", "To test every edge case deeply"),
                    ("B", "To check that critical functionality works after a build or deploy"),
                    ("C", "To measure model accuracy"),
                    ("D", "To replace unit tests"),
                ],
                correct_answer="B",
                explanation="Smoke tests are quick checks of essential functionality.",
                difficulty_level="easy",
            ),
            _RawMCQ(
                question_text="What is a common goal of refactoring?",
                options=[
                    ("A", "To change behavior intentionally without tests"),
                    ("B", "To improve code structure without altering external behavior"),
                    ("C", "To increase the number of bugs"),
                    ("D", "To remove all abstractions"),
                ],
                correct_answer="B",
                explanation="Refactoring improves structure while keeping observable behavior the same.",
                difficulty_level="medium",
            ),
            _RawMCQ(
                question_text="Why is concurrency useful in backend applications?",
                options=[
                    ("A", "It guarantees no race conditions"),
                    ("B", "It helps handle multiple tasks efficiently, especially I/O-bound work"),
                    ("C", "It removes the need for databases"),
                    ("D", "It makes all code deterministic"),
                ],
                correct_answer="B",
                explanation="Concurrency improves throughput and responsiveness for suitable workloads.",
                difficulty_level="medium",
            ),
        ]

    def _adaptive_fillers(
        self,
        role_name: str,
        skills: Sequence[str],
        technologies: Sequence[str],
        years: float,
    ) -> List[_RawMCQ]:
        """
        Create a few polished, role-aware fallback questions when the curated pools are still short.
        These are still distinct and realistic, not placeholders.
        """
        top_skill = skills[0] if skills else "your core domain"
        top_tech = technologies[0] if technologies else "your primary toolset"
        level = "easy" if years < 1 else "medium" if years < 3 else "hard"

        return [
            _RawMCQ(
                question_text=f"For a {role_name} role, what is the best first step when validating a project that uses {top_skill}?",
                options=[
                    ("A", "Deploy immediately without checking outputs"),
                    ("B", "Define a baseline and validate the result against a known reference"),
                    ("C", "Skip evaluation and rely on intuition"),
                    ("D", "Use only production logs for training"),
                ],
                correct_answer="B",
                explanation="A baseline and validation step make the result measurable and trustworthy.",
                difficulty_level=level,
            ),
            _RawMCQ(
                question_text=f"Which approach is most appropriate when debugging a system that uses {top_tech} and shows inconsistent behavior?",
                options=[
                    ("A", "Change multiple components at once"),
                    ("B", "Isolate one variable at a time and compare behavior systematically"),
                    ("C", "Assume the issue is in the frontend only"),
                    ("D", "Disable all logging"),
                ],
                correct_answer="B",
                explanation="Systematic isolation helps identify the real cause of inconsistency.",
                difficulty_level=level,
            ),
            _RawMCQ(
                question_text=f"What is the main reason to document assumptions in a {role_name} project?",
                options=[
                    ("A", "To make the project longer"),
                    ("B", "To keep implementation, evaluation, and maintenance decisions traceable"),
                    ("C", "To avoid using version control"),
                    ("D", "To remove the need for tests"),
                ],
                correct_answer="B",
                explanation="Traceable assumptions make collaboration and maintenance easier.",
                difficulty_level=level,
            ),
            _RawMCQ(
                question_text="Which choice best reflects strong engineering judgment in a production system?",
                options=[
                    ("A", "Optimize only after measurements show a bottleneck"),
                    ("B", "Always choose the most complex design first"),
                    ("C", "Avoid any monitoring to reduce noise"),
                    ("D", "Hardcode environment-specific values"),
                ],
                correct_answer="A",
                explanation="Measured optimization is more reliable than premature complexity.",
                difficulty_level=level,
            ),
            _RawMCQ(
                question_text="When a test result seems suspiciously high, what is the most likely engineering concern?",
                options=[
                    ("A", "Overfitting or data leakage"),
                    ("B", "The server clock is one minute off"),
                    ("C", "The user interface is too simple"),
                    ("D", "The repository has too many files"),
                ],
                correct_answer="A",
                explanation="Inflated results often indicate leakage or overfitting.",
                difficulty_level=level,
            ),
        ]

    def _last_resort_filler(
        self,
        role_name: str,
        skills: Sequence[str],
        technologies: Sequence[str],
        years: float,
        index: int,
    ) -> _RawMCQ:
        """
        A deterministic last-resort filler so the test never falls short of 30.
        """
        top_skill = skills[0] if skills else "fundamentals"
        top_tech = technologies[0] if technologies else "tooling"
        difficulty = "easy" if years < 1 else "medium" if years < 3 else "hard"

        question_text = (
            f"[Supplemental {index}] In a {role_name} assessment, which statement best applies when working with {top_skill} and {top_tech}?"
        )
        return _RawMCQ(
            question_text=question_text,
            options=[
                ("A", "Choose the approach with no validation"),
                ("B", "Use a measurable baseline and verify results carefully"),
                ("C", "Avoid documenting any assumptions"),
                ("D", "Skip testing when time is limited"),
            ],
            correct_answer="B",
            explanation="A measurable baseline and careful verification are the safest default in technical work.",
            difficulty_level=difficulty,
        )

    def _to_mcq_item(self, raw: _RawMCQ) -> MCQItem:
        return MCQItem(
            question_text=raw.question_text,
            options=[MCQOption(key=key, text=text) for key, text in raw.options[:4]],
            correct_answer=raw.correct_answer,
            explanation=raw.explanation,
            difficulty_level=raw.difficulty_level,
        )

    def _normalize_role(self, role_name: str) -> str:
        role = role_name.strip().lower()
        if "ai" in role or "ml" in role or "machine learning" in role:
            return "ai_ml_engineer"
        if "data scientist" in role or "data science" in role:
            return "data_scientist"
        if "backend" in role or "api" in role or "server" in role:
            return "backend_engineer"
        return "generic"

    def _stable_offset(self, seed: str, modulo: int) -> int:
        if modulo <= 0:
            return 0
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % modulo