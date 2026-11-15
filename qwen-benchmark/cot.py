from agent import Agent, log, parse_answer

INSTRUCTIONS = 'Answer the question. Think step by step, then finish with a line "Answer: <answer>".'

EXAMPLES = {
    "hotpotqa": """Question: The Oberoi family is part of a hotel company that has a head office in what city?
Let's think step by step. The Oberoi family is part of The Oberoi Group, a hotel company. The Oberoi Group has its head office in Delhi. So the answer is Delhi.
Answer: Delhi

Question: The Dutch-Belgian television series that "House of Anubis" was based on first aired in what year?
Let's think step by step. House of Anubis is based on the Dutch-Belgian series Het Huis Anubis. Het Huis Anubis first aired in September 2006. So the answer is 2006.
Answer: 2006
""",
    "gsm8k": """Question: Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
Let's think step by step. In May she sold half as many clips as in April, so 48 / 2 = 24 clips. Altogether she sold 48 + 24 = 72 clips.
Answer: 72

Question: Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?
Let's think step by step. Weng earns 12 / 60 = $0.2 per minute. For 50 minutes she earned 0.2 * 50 = $10.
Answer: 10
""",
}


class CoTAgent(Agent):
    """Reasons step by step in free text, then answers."""

    def solve(self, question: str) -> tuple[str, str]:
        prompt = f"{INSTRUCTIONS}\n\n{EXAMPLES[self.dataset]}\nQuestion: {question}\n"
        self.trajectory = self.call(prompt, max_new_tokens=384)
        answer, found = parse_answer(self.trajectory, self.dataset)
        thinking = self.trajectory.rsplit("Answer:", 1)[0] if found else self.trajectory
        self.thinking_tokens = self.lm.count_tokens(thinking)
        log("finish", prediction=answer, reason="answer" if found else "parse_error")
        return answer, "answer" if found else "parse_error"
