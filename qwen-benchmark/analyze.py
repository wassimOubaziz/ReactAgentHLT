import json
import random
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from scipy.stats import binomtest  # noqa: E402

from data import load_hotpotqa  # noqa: E402
from tools import Search, paragraphs  # noqa: E402

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
DATASETS = {"hotpotqa": "HotPotQA", "gsm8k": "GSM8K"}
AGENT_LABELS = {"default": "Standard", "cot": "CoT", "react": "ReAct", "focused": "Focused ReAct"}
AGENT_ORDER = ["Standard", "CoT", "ReAct", "Focused ReAct", "ReAct (dense)", "Focused ReAct (dense)"]
METRICS = ["em", "f1", "input_tokens", "output_tokens", "thinking_tokens", "observation_tokens", "steps", "latency_s"]
STOPS = ["answer", "max_steps", "early_stop", "parse_error"]
PAIRS = [("cot", "default"), ("react", "cot"), ("focused", "react")]


def load(results: Path | None = None) -> pd.DataFrame:
    root = results or RESULTS
    rows = []
    for path in sorted(root.rglob("*.jsonl")):
        run = path.parent.name if path.parent != root else "default"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                row["run"] = run
                rows.append(row)
    df = pd.DataFrame(rows)
    df[["precision", "recall", "f1"]] = df[["precision", "recall", "f1"]].astype(float)
    df["total_tokens"] = df.input_tokens + df.output_tokens
    df["agent_label"] = df.agent.map(AGENT_LABELS)
    df.loc[df.retriever == "dense", "agent_label"] += " (dense)"
    return df


def ci95(values) -> float:
    x = np.asarray(pd.Series(values).dropna(), dtype=float)
    if len(x) < 2:
        return float("nan")
    means = np.random.default_rng(0).choice(x, size=(2000, len(x))).mean(axis=1)
    return float(np.percentile(means, 97.5) - np.percentile(means, 2.5)) / 2


def present_datasets(df: pd.DataFrame) -> list[str]:
    return [d for d in DATASETS if d in set(df.dataset)]


def order_of(df: pd.DataFrame) -> list[str]:
    return [label for label in AGENT_ORDER if label in set(df.agent_label)]


def by_order(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("agent_label", key=lambda s: s.map(AGENT_ORDER.index))


def per_agent_n(df: pd.DataFrame) -> int:
    return int(df.groupby("agent_label").size().max())


def save(fig, name: str) -> None:
    fig.tight_layout()
    path = FIGURES / name
    for attempt in range(4):  # Windows occasionally returns EINVAL while a freshly written PNG is scanned
        try:
            fig.savefig(path, dpi=200)
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(0.5)
    plt.close(fig)
    print("saved", name)


def panels(n: int, width: float = 6.0, height: float = 4.5):
    fig, axes = plt.subplots(1, n, figsize=(width * n, height), squeeze=False)
    return fig, axes[0]


def fig_accuracy(df: pd.DataFrame) -> None:
    dsets = present_datasets(df)
    fig, axes = panels(len(dsets))
    for ax, ds in zip(axes, dsets):
        sub = df[df.dataset == ds]
        sns.barplot(data=sub, x="agent_label", y="em", hue="model", order=order_of(sub), errorbar=("ci", 95), ax=ax)
        ax.set(title=f"{DATASETS[ds]} exact match (N={per_agent_n(sub)})", xlabel="Agent",
               ylabel="Exact match (fraction correct)", ylim=(0, 1))
        ax.tick_params(axis="x", rotation=15)
    save(fig, "fig1_accuracy.png")


def fig_f1(df: pd.DataFrame) -> None:
    sub = df[df.dataset == "hotpotqa"]
    if sub.empty:
        print("skipped fig1b: no HotPotQA data")
        return
    fig, axes = panels(3, width=5.5)
    for ax, metric, name in zip(axes, ["f1", "precision", "recall"], ["F1", "Precision", "Recall"]):
        sns.barplot(data=sub, x="agent_label", y=metric, hue="model", order=order_of(sub), errorbar=("ci", 95), ax=ax)
        ax.set(title=f"HotPotQA {name} (N={per_agent_n(sub)})", xlabel="Agent", ylabel=f"{name} (fraction)", ylim=(0, 1))
        ax.tick_params(axis="x", rotation=15)
    save(fig, "fig1b_f1_hotpotqa.png")


def fig_tokens(df: pd.DataFrame) -> None:
    dsets = present_datasets(df)
    fig, axes = panels(len(dsets))
    for ax, ds in zip(axes, dsets):
        sub = df[df.dataset == ds]
        g = by_order(sub.groupby(["agent_label", "model"]).agg(
            inp=("input_tokens", "mean"), out=("output_tokens", "mean")).reset_index())
        x = np.arange(len(g))
        ax.bar(x, g.inp, label="Input tokens (prompt)")
        ax.bar(x, g.out, bottom=g.inp, label="Output tokens (generated)")
        ax.set_xticks(x, [f"{a}\n{m}" for a, m in zip(g.agent_label, g.model)], fontsize=8)
        ax.set(title=f"{DATASETS[ds]} tokens per question (N={per_agent_n(sub)})", xlabel="Agent and model",
               ylabel="Mean tokens per question")
        ax.legend()
    save(fig, "fig2_tokens.png")


def fig_breakdown(df: pd.DataFrame) -> None:
    dsets = present_datasets(df)
    fig, axes = panels(len(dsets))
    for ax, ds in zip(axes, dsets):
        sub = df[df.dataset == ds]
        g = by_order(sub.groupby(["agent_label", "model"]).agg(
            think=("thinking_tokens", "sum"), out=("output_tokens", "sum")).reset_index())
        share = (g.think / g.out).fillna(0).clip(0, 1).to_numpy() * 100
        x = np.arange(len(g))
        ax.bar(x, share, label="Thinking tokens")
        ax.bar(x, 100 - share, bottom=share, label="Answer / action tokens")
        ax.set_xticks(x, [f"{a}\n{m}" for a, m in zip(g.agent_label, g.model)], fontsize=8)
        ax.set(title=f"{DATASETS[ds]} output token breakdown (N={per_agent_n(sub)})", xlabel="Agent and model",
               ylabel="Share of output tokens (%)", ylim=(0, 100))
        ax.legend()
    save(fig, "fig3_output_breakdown.png")


def fig_latency(df: pd.DataFrame) -> None:
    dsets = present_datasets(df)
    fig, axes = panels(len(dsets))
    for ax, ds in zip(axes, dsets):
        sub = df[df.dataset == ds]
        sns.boxplot(data=sub, x="agent_label", y="latency_s", hue="model", order=order_of(sub), ax=ax)
        ax.set(title=f"{DATASETS[ds]} latency per question (N={per_agent_n(sub)})", xlabel="Agent",
               ylabel="End-to-end latency per question (s)")
        ax.tick_params(axis="x", rotation=15)
    save(fig, "fig4_latency.png")


def fig_efficiency(df: pd.DataFrame, xcol: str, name: str, xlabel: str) -> None:
    dsets = present_datasets(df)
    fig, axes = panels(len(dsets), width=7)
    for ax, ds in zip(axes, dsets):
        sub = df[df.dataset == ds]
        g = sub.groupby(["agent_label", "model"]).agg(
            x=(xcol, "mean"), acc=("em", "mean")).reset_index()
        sns.scatterplot(data=g, x="x", y="acc", hue="model", style="agent_label", s=120, ax=ax)
        for _, r in g.iterrows():
            ax.annotate(r.agent_label, (r.x, r.acc), xytext=(5, 5), textcoords="offset points", fontsize=8)
        ax.set(xscale="log", title=f"{DATASETS[ds]} accuracy vs cost (N={per_agent_n(sub)})", xlabel=xlabel,
               ylabel="Accuracy (exact match, fraction)", ylim=(-0.05, 1.05))
    save(fig, name)


def fig_steps(df: pd.DataFrame) -> None:
    sub = df[df.agent.isin(["react", "focused"]) & df.retriever.isin(["none", "sparse"])]
    if sub.empty:
        print("skipped fig6: no ReAct / Focused data")
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    sns.histplot(data=sub, x="steps", hue="agent_label", hue_order=order_of(sub), discrete=True,
                 multiple="dodge", shrink=0.8, ax=ax1)
    ax1.set(title=f"Number of LLM calls per question (N={per_agent_n(sub)} per agent)", xlabel="LLM calls (steps)")
    sns.barplot(data=sub, x="steps", y="em", hue="agent_label", hue_order=order_of(sub),
                errorbar=("ci", 95), ax=ax2)
    ax2.set(title="Exact match by number of LLM calls", xlabel="LLM calls (steps)",
            ylabel="Exact match (fraction correct)", ylim=(0, 1))
    save(fig, "fig6_react_steps.png")


def fig_stops(df: pd.DataFrame) -> None:
    sub = df[df.agent.isin(["react", "focused"]) & df.retriever.isin(["none", "sparse"])]
    dsets = present_datasets(sub)
    if not dsets:
        print("skipped fig7: no ReAct / Focused data")
        return
    fig, axes = panels(len(dsets))
    for ax, ds in zip(axes, dsets):
        s = sub[sub.dataset == ds]
        share = pd.crosstab([s.model, s.agent_label], s.stop_reason, normalize="index")
        share = share.reindex(columns=STOPS, fill_value=0)
        x = np.arange(len(share))
        bottom = np.zeros(len(share))
        for stop in STOPS:
            ax.bar(x, share[stop].to_numpy() * 100, bottom=bottom, label=stop)
            bottom += share[stop].to_numpy() * 100
        ax.set_xticks(x, [f"{m}\n{a}" for m, a in share.index], fontsize=8)
        ax.set(title=f"{DATASETS[ds]} stop reasons (N={per_agent_n(s)})", xlabel="Model and agent",
               ylabel="Share of questions (%)", ylim=(0, 100))
        ax.legend(title="Stop reason")
    save(fig, "fig7_stop_reasons.png")


def fig_retrieval(df: pd.DataFrame) -> None:
    hotpot = df[df.dataset == "hotpotqa"]
    if hotpot.empty:
        print("skipped fig8: no HotPotQA data")
        return
    items = load_hotpotqa(hotpot.id.nunique())
    paras = paragraphs(items)
    recall_rows = []
    for kind in ["sparse", "dense"]:
        search = Search(paras, kind=kind, k=3)
        for item in items:
            hit = len(set(search.titles(item["question"])) & set(item["gold_titles"]))
            recall_rows.append({"retriever": kind, "recall_at_3": hit / len(item["gold_titles"])})
    recall = pd.DataFrame(recall_rows)
    react = hotpot[(hotpot.agent == "react") & hotpot.retriever.isin(["sparse", "dense"])]
    fig, axes = panels(2 if not react.empty else 1, width=6)
    sns.barplot(data=recall, x="retriever", y="recall_at_3", errorbar=("ci", 95), ax=axes[0])
    axes[0].set(title=f"Gold-title recall@3 from the raw question (N={len(items)})", xlabel="Retriever",
                ylabel="Recall@3 (fraction of gold titles)", ylim=(0, 1))
    if not react.empty:
        sns.barplot(data=react, x="retriever", y="em", errorbar=("ci", 95), ax=axes[1])
        axes[1].set(title=f"ReAct exact match by retriever (N={per_agent_n(react.assign(agent_label=react.retriever))})",
                    xlabel="Retriever", ylabel="Exact match (fraction correct)", ylim=(0, 1))
    save(fig, "fig8_retrieval.png")


def write_summary(df: pd.DataFrame) -> None:
    rows = []
    keys = ["dataset", "model", "agent_label"] + (["run"] if df.run.nunique() > 1 else [])
    for group, g in df.groupby(keys, sort=False):
        ds, model, label = group[0], group[1], group[2]
        run = group[3] if len(group) > 3 else "default"
        row = {"dataset": ds, "model": model, "agent": label, "run": run, "N": len(g)}
        for m in METRICS:
            row[f"{m}_mean"] = g[m].mean()
            row[f"{m}_ci95"] = ci95(g[m])
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(FIGURES / "summary.csv", index=False)

    def cell(mean: float, ci: float) -> str:
        return "–" if pd.isna(mean) else f"{mean:.3f} ± {ci:.3f}"

    head = ["Dataset", "Model", "Agent", "N", "EM", "F1", "Input tok", "Output tok", "Thinking tok",
            "Observation tok", "Steps", "Latency (s)"]
    lines = ["# Summary (mean ± 95% bootstrap CI)", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for _, r in table.iterrows():
        cells = [DATASETS[r.dataset], r.model, r.agent, str(r.N)]
        cells += [cell(r[f"{m}_mean"], r[f"{m}_ci95"]) for m in METRICS]
        lines.append("| " + " | ".join(cells) + " |")
    lines += ["", "## Tokens per correct answer (total input + output tokens / number correct)", "",
              "| Dataset | Model | Agent | Tokens per correct |", "|---|---|---|---|"]
    per_correct = tokens_per_correct(df)
    for _, r in per_correct.iterrows():
        value = "–" if pd.isna(r.tokens_per_correct) else f"{r.tokens_per_correct:.0f}"
        lines.append(f"| {DATASETS[r.dataset]} | {r.model} | {r.agent_label} | {value} |")
    (FIGURES / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def tokens_per_correct(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["dataset", "model", "agent_label"]).agg(
        total_tokens=("total_tokens", "sum"), correct=("correct", "sum")).reset_index()
    g["tokens_per_correct"] = g.total_tokens / g.correct.replace(0, np.nan)
    g.to_csv(FIGURES / "tokens_per_correct.csv", index=False)
    return g


def write_significance(df: pd.DataFrame) -> None:
    base = df[df.retriever.isin(["none", "sparse"])]
    rows = []
    for ds, model in base[["dataset", "model"]].drop_duplicates().itertuples(index=False):
        for a, b in PAIRS:
            pick = base[(base.dataset == ds) & (base.model == model)]
            A = pick[pick.agent == a].set_index("id").correct.rename("a")
            B = pick[pick.agent == b].set_index("id").correct.rename("b")
            both = pd.concat([A, B], axis=1, join="inner")
            a_only = int((both.a & ~both.b).sum())
            b_only = int((~both.a & both.b).sum())
            n_disc = a_only + b_only
            p = binomtest(a_only, n_disc, 0.5).pvalue if n_disc else 1.0
            rows.append({
                "dataset": ds, "model": model, "comparison": f"{AGENT_LABELS[a]} vs {AGENT_LABELS[b]}",
                "n_paired": len(both), "first_right_second_wrong": a_only,
                "first_wrong_second_right": b_only, "p_value": p,
            })
    pd.DataFrame(rows).to_csv(FIGURES / "significance.csv", index=False)


def write_failures(df: pd.DataFrame) -> None:
    rng = random.Random(0)
    base = df[df.retriever.isin(["none", "sparse"])]
    out = ["# Failure examples", "", "Five random wrong answers per (dataset, agent), random seed 0.", ""]
    for (ds, label), g in base.groupby(["dataset", "agent_label"], sort=False):
        wrong = g[~g.correct].reset_index(drop=True)
        out += [f"## {DATASETS[ds]} · {label} (wrong: {len(wrong)} of {len(g)})", ""]
        for i in sorted(rng.sample(range(len(wrong)), min(5, len(wrong)))):
            r = wrong.iloc[i]
            out += [f"### {r.question}", f"- gold: `{r.gold}`", f"- prediction: `{r.prediction}`",
                    f"- stop reason: {r.stop_reason}, LLM calls: {r.steps}", "", "```text",
                    r.trajectory.strip(), "```", ""]
    (FIGURES / "failures.md").write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build figures and tables from results/")
    parser.add_argument("--results-dir", default=str(RESULTS), help="results folder; use a run-specific subfolder")
    args = parser.parse_args()
    sns.set_theme(style="whitegrid", palette="colorblind")
    FIGURES.mkdir(exist_ok=True)
    df = load(Path(args.results_dir))
    fig_accuracy(df)
    fig_f1(df)
    fig_tokens(df)
    fig_breakdown(df)
    fig_latency(df)
    fig_efficiency(df, "total_tokens", "fig5_efficiency.png", "Mean total tokens per question (input + output, log scale)")
    fig_efficiency(df, "latency_s", "fig5b_accuracy_vs_latency.png", "Mean latency per question (s, log scale)")
    fig_steps(df)
    fig_stops(df)
    fig_retrieval(df)
    write_summary(df)
    write_significance(df)
    write_failures(df)


if __name__ == "__main__":
    main()
