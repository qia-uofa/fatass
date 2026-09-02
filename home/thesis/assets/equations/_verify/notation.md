Checked home/thesis/assets/equations/_.md for symbol consistency. Found several real collisions where the same symbol denotes different quantities in different equations (font/case is identical, so a reader can't tell them apart from notation alone):

1. **`e_i` collides between two unrelated meanings.**
   - In §0.1, eq. (P1)/(P2) region, the offset mapping is defined as OFF(u)_i = (b_i, e_i), so e_i is the character-span *end* of token i.
   - In §1.2, eq. (8), a TriviaQA seed is s_i = (q_i, e_i, A_i) with "e_i = A_{i,1}" — here e_i is the reference-answer string (the first gold alias).
   Both are indexed by i and both are called e_i, but one is an integer offset and the other is a string. Recommend renaming one (e.g. keep e_i for offsets, use e.g. ā_i or ref_i for the reference answer).

2. **`R` is used for three different objects.**
   - §1.2: "Let R be the raw `rc.nocontext` validation split" — R is a dataset/table.
   - §1.5, eqs. (19)–(20): R (and R_t, R_0) denotes the *remaining candidate set* in a 20-questions game.
   - §5.2, eq. (56): "(ω_1,…,ω_R)" — R is the *count* of observation methods (a matrix dimension).
   Three incompatible uses of the same bare letter R (raw split / evolving candidate set / integer count) in the same document.

3. **`P` is used for three different objects.**
   - Eq. (4): P_C(w) is a frequency *distribution* over keywords.
   - Eq. (29): P(t_i | t_{<i}, x_0(q)) is a *probability* (of a token given context).
   - Eqs. (65)–(66): P = |Θ_ext^γ| is a *pool size* (an integer cardinality), then indexed as θ_[1],…,θ_[P].
   P-as-distribution, P-as-probability, and P-as-cardinality all appear without being distinguished typographically.

4. **`b` collides, more mildly.**
   - §0.1: b_i is the character-span *start* of token i (paired with e_i above).
   - Eq. (68): b = ⌊n_test/2⌋ is a plain integer (half the test-set size).
   Same letter, unrelated meanings, though the local contexts are far apart and less likely to actually confuse a reader than #1–#3.

Everything else checked out as consistent: ω/Ω for observation methods, γ/Γ for ground truths, θ/Θ for trials/pools, h^(ℓ)_p for residual activations, v/v_0 for steering vectors, α for steering strength, Δ_logit for the logit-difference metric, K/K classes, N as a per-equation sample count (§0.3, §5.1, §6.7 all locally define N as "the pool/sample size in this computation," which is a standard, unambiguous reuse rather than a true collision), n_tok, m_ω, ρ, μ(·), sem(·) are all used the same way everywhere they appear.

One non-notational inconsistency worth flagging since it touches the same "does the symbol mean what it's claimed to mean" concern: in §4.4, the text itself states that eq. (49)'s formula for γ_chal computes *increasing-in-caving* (higher = model caved more), while "The class docstring describes the opposite polarity." This is flagged in the source already but is a real semantic inconsistency in what γ_chal denotes vs. what code/prose claims it denotes, not just a typographic collision.
