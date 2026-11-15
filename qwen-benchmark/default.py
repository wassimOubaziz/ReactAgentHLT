from agent import Agent, log, parse_answer

INSTRUCTIONS = 'Answer the question. Reply only in the form "Answer: <answer>" with no explanation.'

EXAMPLES = {
    "hotpotqa": """Question: The Oberoi family is part of a hotel company that has a head office in what city?
Answer: Delhi

Question: The Dutch-Belgian television series that "House of Anubis" was based on first aired in what year?
Answer: 2006
""",
    "gsm8k": """Question: Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
Answer: 72

Question: Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?
Answer: 10
""",
}


class StandardAgent(Agent):
    """Answers directly, without thinking."""

    def solve(self, question: str) -> tuple[str, str]:
        prompt = f"{INSTRUCTIONS}\n\n{EXAMPLES[self.dataset]}\nQuestion: {question}\n"
        self.trajectory = self.call(prompt, max_new_tokens=64)
        answer, found = parse_answer(self.trajectory, self.dataset)
        log("finish", prediction=answer, reason="answer" if found else "parse_error")
        return answer, "answer" if found else "parse_error"
