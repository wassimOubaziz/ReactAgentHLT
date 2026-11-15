import re

from agent import Agent, fallback_answer, log, viewing

TOOL_SYNTAX = {"hotpotqa": "Search[...]", "gsm8k": "Calculate[...]"}

INSTRUCTIONS = {
    "hotpotqa": """Answer the question by interleaving Thought, Action and Observation steps.
Actions:
Search[query] returns the best matching passages for the query.
Finish[answer] ends the task with the final answer.
In each step write exactly one Thought: line and one Action: line, then stop. Never write Observation: yourself.""",
    "gsm8k": """Solve the math word problem by interleaving Thought, Action and Observation steps.
Actions:
Calculate[expression] evaluates an arithmetic expression, for example Calculate[3 * (4 + 5)].
Finish[answer] ends the task with the final numeric answer.
In each step write exactly one Thought: line and one Action: line, then stop. Never write Observation: yourself.""",
}

EXAMPLES = {
    "hotpotqa": """Question: The Oberoi family is part of a hotel company that has a head office in what city?
Thought: I need to search the Oberoi family and find the hotel company it is part of.
Action: Search[Oberoi family]
Observation: [Oberoi family] The Oberoi family is an Indian family that is famous for its involvement in hotels, namely through The Oberoi Group.
Thought: The Oberoi family is part of The Oberoi Group. I need to search The Oberoi Group to find its head office.
Action: Search[The Oberoi Group]
Observation: [The Oberoi Group] The Oberoi Group is a hotel company with its head office in Delhi. Founded in 1934, the company owns and/or operates 30+ luxury hotels ...
Thought: The Oberoi Group has its head office in Delhi. So the answer is Delhi.
Action: Finish[Delhi]

Question: The Dutch-Belgian television series that "House of Anubis" was based on first aired in what year?
Thought: I need to search House of Anubis and find the Dutch-Belgian series it is based on.
Action: Search[House of Anubis]
Observation: [House of Anubis] House of Anubis is a mystery television series developed for Nickelodeon based on the Dutch-Belgian television series "Het Huis Anubis". ...
Thought: The series is Het Huis Anubis. I need to search it to find when it first aired.
Action: Search[Het Huis Anubis]
Observation: [Het Huis Anubis] Het Huis Anubis ("The House of Anubis") is a Belgian-Dutch children's television drama created by Studio 100 and Nickelodeon, airing in the Netherlands and Flanders. It first aired in September 2006 ...
Thought: It first aired in September 2006. So the answer is 2006.
Action: Finish[2006]
""",
    "gsm8k": """Question: Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
Thought: In May she sold half of 48 clips, so I need 48 / 2 and then add 48.
Action: Calculate[48 + 48 / 2]
Observation: 72
Thought: Natalia sold 72 clips altogether. So the answer is 72.
Action: Finish[72]

Question: Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn?
Thought: Weng earns 12 / 60 dollars per minute, so for 50 minutes I need 12 / 60 * 50.
Action: Calculate[12 / 60 * 50]
Observation: 10
Thought: She earned 10 dollars. So the answer is 10.
Action: Finish[10]
""",
}

FORCE = ("The tool budget is exhausted. Search and Calculate are no longer available. "
         "Do not call any tool. Answer only from the observations above. "
         "Reply with exactly one line: Action: Finish[<final answer>]")

PLACEHOLDERS = {"answer", "final answer", "your answer"}


def parse_finish(text: str) -> str | None:
    """Answer from a Finish[...] anywhere, with or without the Action: prefix."""
    match = re.search(r"Finish\[(.*?)\]", text, re.S)
    if not match:
        return None
    answer = match.group(1).strip()
    if answer.startswith("<") and answer.endswith(">"):
        answer = answer[1:-1].strip()
    return None if answer.lower() in PLACEHOLDERS else answer or None


def parse_step(text: str, tools: list[str]) -> tuple[str, tuple[str, str] | None]:
    """Thought and (tool, argument) from the FIRST Action line; anything after it is ignored."""
    head, found, rest = text.partition("Action:")
    thought = head.replace("Thought:", "", 1).strip()
    if not found:
        return thought, None
    match = re.match(r"\s*(\w+)\[(.*?)\]", rest.split("\n", 1)[0])
    if match and match.group(1) in tools:
        return thought, (match.group(1), match.group(2).strip())
    return thought, None


class ReActAgent(Agent):
    """Thought / Action / Observation loop with a budget of max_steps LLM calls."""

    max_steps = 7

    def build_prompt(self, question: str, scratchpad: str) -> str:
        return f"{INSTRUCTIONS[self.dataset]}\n\n{EXAMPLES[self.dataset]}\nQuestion: {question}\n{scratchpad}"

    def should_stop(self, history: list) -> str | None:
        return None

    def think_act(self, prompt: str) -> tuple[str, str, tuple[str, str] | None]:
        text = self.call(prompt, max_new_tokens=160, stop=["Observation:"])
        thought, action = parse_step(text, [*self.tools, "Finish"])
        self.thinking_tokens += self.lm.count_tokens(thought)
        log("thought", text=thought, tokens=self.lm.count_tokens(thought))
        if action:
            log("action", tool=action[0], argument=action[1])
        else:
            log("invalid_action", text=text)
        return text, thought, action

    def solve(self, question: str) -> tuple[str, str]:
        scratchpad, history = "", []
        for _ in range(self.max_steps):
            _, thought, action = self.think_act(self.build_prompt(question, scratchpad))
            if action and action[0] == "Finish":
                self.trajectory = scratchpad + f"Thought: {thought}\nAction: Finish[{action[1]}]\n"
                log("finish", prediction=action[1], reason="answer")
                return action[1], "answer"
            if action is None:
                step = f"Thought: {thought}\n"
                obs = f"Invalid action. Use {TOOL_SYNTAX[self.dataset]} or Finish[...]."
                history.append(None)
            else:
                tool, arg = action
                hits = self.tools[tool].retrieve(arg) if tool == "Search" and viewing() else None
                obs = self.tools[tool](arg)
                log("tool_result", tool=tool, argument=arg, text=obs, hits=hits)
                step = f"Thought: {thought}\nAction: {tool}[{arg}]\n"
                history.append((tool, " ".join(arg.lower().split())))
            log("observation", text=obs, tokens=self.lm.count_tokens(obs))
            scratchpad += f"{step}Observation: {obs}\n"
            self.observation_tokens += self.lm.count_tokens(obs)
            reason = self.should_stop(history)
            if reason:
                log("stop", reason=reason)
                return self.force_answer(question, scratchpad, reason)
        self.trajectory = scratchpad
        log("finish", prediction="", reason="max_steps")
        return "", "max_steps"

    def force_answer(self, question: str, scratchpad: str, reason: str) -> tuple[str, str]:
        scratchpad += FORCE + "\n"
        text, _, action = self.think_act(self.build_prompt(question, scratchpad))
        self.trajectory = scratchpad + text
        prediction = action[1] if action and action[0] == "Finish" else parse_finish(text)
        if prediction:
            log("finish", prediction=prediction, reason=reason)
            return prediction, reason
        prediction = fallback_answer(text, self.dataset)
        log("finish", prediction=prediction, reason="parse_error")
        return prediction, "parse_error"
