from react import ReActAgent


class FocusedReActAgent(ReActAgent):
    """ReAct that restates the original question at the end of every prompt and stops early on loops."""

    def build_prompt(self, question: str, scratchpad: str) -> str:
        return super().build_prompt(question, scratchpad) + (
            f"Original question: {question}\nStay on this question only. Next step:"
        )

    def should_stop(self, history: list) -> str | None:
        if len(history) >= 2 and history[-1] is None and history[-2] is None:
            return "early_stop"
        if history and history[-1] is not None and history.count(history[-1]) > 1:
            return "early_stop"
        if len(history) >= self.max_steps:
            return "max_steps"
        return None
