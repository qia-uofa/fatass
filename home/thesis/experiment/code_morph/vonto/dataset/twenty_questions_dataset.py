"""Twenty questions: every game fully played out at generation time — see
`TwentyQuestionsDataset`'s docstring."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from .. import twenty_questions as TQ
from .dataset import CATEGORY, Dataset, Inquiry, sample


@dataclass
class Game:
    """One played-out 20-Questions game. ``history`` is the full turn-by-turn
    transcript, played during `TwentyQuestionsDataset.generate()` itself."""

    keywords: tuple[str, ...]
    secret: str
    T: int
    history: list = field(default_factory=list)  # [(question, answer), ...]

    def history_str(self) -> str:
        return "\n".join(f"Q: {q}\nA: {a}" for q, a in self.history) or "(no questions yet)"

    @property
    def precomputed_response(self) -> str:
        """The real last question the model actually asked during play
        (``history``'s own last entry) — duck-typed hook `generation.
        generate_trial` checks for, so calibration scores *this* question
        (the one that actually determined the game's induced partition)
        instead of resynthesizing an unrelated one under a differently-framed
        prompt (see `TwentyQuestionsDataset.inquiry`'s own docstring)."""
        return self.history[-1][0]


def _generate_text(loaded, prompt: str | list[dict[str, str]], max_new_tokens: int) -> str:
    """One greedy generation — chat-templated if ``prompt`` is a message list,
    raw text otherwise."""
    import torch

    messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]
    text = loaded.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    enc = loaded.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(loaded.device)
    with torch.no_grad():
        out = loaded.model.generate(
            **enc, max_new_tokens=max_new_tokens, do_sample=False, temperature=None, top_p=None,
            top_k=None, repetition_penalty=1.0, pad_token_id=loaded.tokenizer.pad_token_id,
        )
    new_tokens = out[:, enc["input_ids"].shape[1] :]
    return loaded.tokenizer.decode(new_tokens[0], skip_special_tokens=True).strip()


class TwentyQuestionsDataset(Dataset):
    """Plays ``len(CATEGORY) * n_games`` full 20-Questions games at generation
    time (real model calls: two generations per turn, ``T`` turns per game) —
    expensive enough that progress checkpoints to ``checkpoint_path`` after
    every game, so an interrupted run resumes instead of replaying
    already-played games.
    """

    seed_cls = Game

    def shape_params(self) -> dict[str, object]:
        return {"n_games": self.n_games, "k": self.k, "T": self.T}

    def _seed_from_dict(self, blob: dict) -> Game:
        return Game(
            keywords=tuple(blob["keywords"]), secret=blob["secret"], T=blob["T"],
            history=[tuple(turn) for turn in blob["history"]],
        )

    def __init__(
        self, loaded, n_games: int, k: int, T: int, rng_seed: int = 0,
        checkpoint_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.loaded = loaded
        self.n_games, self.k, self.T = n_games, k, T
        self.rng_seed = rng_seed
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None

    def _play_one_game(self, keywords: tuple[str, ...], secret: str) -> Game:
        history: list[tuple[str, str]] = []
        remaining = keywords
        for _ in range(self.T):
            messages = TQ.build_conversation_for_next_question(keywords, history)
            question = _generate_text(self.loaded, messages, max_new_tokens=40)
            partition_text = _generate_text(
                self.loaded, TQ.build_partition_prompt(question, remaining), max_new_tokens=600
            )
            yes_set, no_set = TQ.parse_partition(partition_text, remaining)
            answer = "Yes" if secret in yes_set else "No"
            history.append((question, answer))
            remaining = yes_set if secret in yes_set else no_set
        return Game(keywords=keywords, secret=secret, T=self.T, history=history)

    def _load_checkpoint(self) -> list[Game]:
        if not (self.checkpoint_path and self.checkpoint_path.exists()):
            return []
        return [self._seed_from_dict(blob) for blob in json.loads(self.checkpoint_path.read_text())]

    def _save_checkpoint(self) -> None:
        if self.checkpoint_path:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            self.checkpoint_path.write_text(json.dumps([asdict(g) for g in self.seeds], indent=1))

    def generate(self) -> None:
        self.seeds = self._load_checkpoint()
        stale = any(len(g.keywords) != self.k or g.T != self.T for g in self.seeds)
        if stale:
            print(
                f"[TwentyQuestionsDataset] checkpoint at {self.checkpoint_path} was written with "
                f"different (k, T) settings -- discarding it and replaying from scratch"
            )
            self.seeds = []

        target = len(CATEGORY) * self.n_games
        already = len(self.seeds)
        if already >= target:
            print(f"[TwentyQuestionsDataset] loaded {target} already-played games from checkpoint")
            self.seeds = self.seeds[:target]
            return
        if already:
            print(f"[TwentyQuestionsDataset] resuming from checkpoint: {already}/{target} games already played")

        index = 0
        for category in CATEGORY:
            for _ in range(self.n_games):
                if index < already:
                    index += 1
                    continue
                # Seeded by (rng_seed, index), not a shared mutable RNG stream,
                # so a resumed run draws exactly the same (keywords, secret) a
                # from-scratch run would have at this index.
                draw_rng = np.random.default_rng((self.rng_seed, index))
                keywords = sample(category, self.k, seed=int(draw_rng.integers(0, 2**31)))
                secret = keywords[int(draw_rng.integers(0, len(keywords)))]
                self.seeds.append(self._play_one_game(keywords, secret))
                self._save_checkpoint()
                index += 1
                print(f"[TwentyQuestionsDataset] played {index}/{target} games ({category})")

    def inquiry(self, seed: Game) -> Inquiry:
        # Record-keeping only now (`Trial.inquiry`) -- `Game.precomputed_response`
        # (`seed.history[-1][0]`, the real question actually asked) is what
        # `generation.generate_trial` actually scores, bypassing generation
        # entirely; this text is never itself sent to the model. Restated
        # here anyway, as a plain description of the decision point, rather
        # than left blank -- a `Trial.inquiry.question` other code reads
        # (e.g. `compose_self_report_inquiry`) should describe the real
        # situation, not be empty just because nothing gets generated from it.
        #
        # temperature=0 -- greedy. Unlike ListElicitationDataset, `Game`
        # carries no genuine per-seed temperature of its own to use; a bare
        # hardcoded nonzero value here would just be arbitrary noise, not a
        # real "seed temperature" the way ListElicitationSeed.temperature is.
        return Inquiry(
            f"You are playing 20 Questions. The keyword universe is: "
            f"{', '.join(seed.keywords)}.\n{seed.history_str()}\nWhat is your next Yes/No question?",
            0.0,
            0,
        )
