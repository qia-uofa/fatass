## Phase 0 Preparation

### Prepare Dataset
#### Download
- TriviaQA
- Philpapers
- Ethics

#### Generate
CATEGORY = Handpick 10 categories (7 concrete, 3 abstract)
def sample(category, n) := sample n keywords form category, according to natural frequency, no repeat

```
structure Inquiry = (
    question:str, 
    temperature:float, 
    generation_seed:int
)

class Dataset:
    @subclasstodo
    structure Seed

    seeds : [Seed] = []

    @subclasstodo
    generate : () -> void

    @subclasstodo
    inquiry : Seed -> Inquiry


#: Alternate phrasings of "the question + the answer" a downloaded dataset's
#: raw (question, answer) pair can be turned into. Hardcoded here, once, so
#: every downloaded dataset picks from the same named set rather than each
#: inventing its own phrasing.
def DIRECT_QUESTION(question, answer) := question
def BINARY_JUDGMENT_QUESTION(question, answer) := "Is the answer to \"{question}\" \"{answer}\"? Answer Yes or No."

class DownloadedDataset(Dataset):
    raw_question : str -> str -> str  # DIRECT_QUESTION | BINARY_JUDGMENT_QUESTION

    @subclasstodo
    download_and_load : () -> [Seed]

    def generate():
        this.seeds = this.download_and_load()


class TriviaQA(DownloadedDataset):
    structure Seed = (
        trivia_question:str,
        answer:str
    )

    def download_and_load():
        raw = download("triviaqa")
        return [Seed(item.question, item.answer) for item in load(raw)]

    def inquiry(seed):
        return Inquiry(
            this.raw_question(seed.trivia_question, seed.answer),
            0.7,
            None
        )


class Philpapers(DownloadedDataset):
    # TODO: Seed shape + download_and_load + inquiry, same pattern as TriviaQA

class Ethics(DownloadedDataset):
    # TODO: Seed shape + download_and_load + inquiry, same pattern as TriviaQA


class SynonymsDataset(Dataset):
    n : int 
    N : int
    d : float
    question : str -> str -> str

    structure Seed = (
        keyword:str, 
        synonym:str, 
        distance:float
    )

    def generate():
        for category in CATEGORY:
            keywords = sample(category, n)
            for keyword in keywords:
                for distance in 1..N:
                    synonym = decode(encode(keyword) + distance * d * encode("synonym"))
                    this.seeds.append(Seed(keyword, synonym, distance))

    def inquiry(seed):
        return Inquiry(
            question(seed.keyword, seed.synonym),
            0.7,
            None
        )

class ListElicitationDataset(Dataset):
    n : int
    k : int

    structure Seed = (
        keyword:str,
        temperature:float,
        generation_seed:int
    )

    def generate():
        for category in CATEGORY:
            keywords = sample(category, n)
            for keyword in keywords:
                temperature = uniform(0, 1)
                generation_seed = random()
                this.seeds.append(Seed(keyword, temperature, generation_seed))

    def inquiry(seed):
        return Inquiry(
            "Give me a list of {this.k} things, starting with {seed.keyword}.",
            seed.temperature,
            seed.generation_seed
    )

class TwentyQuestionsDataset(Dataset):
    n : int
    k : int
    T : int

    structure Seed = Game

    def generate():
        for category in CATEGORY:
            for i in 1..n:
                keywords = sample(category, k)
                secret = random_choice(keywords)
                game = generate_game(keywords, secret, this.T)
                this.seeds.append(game)

    def inquiry(seed):
        return Inquiry(
            """
                You are playing ... {seed.keywords}...{seed.history_str()} ... What is your next question?
            """, 
            0.7,
            None
        )


```
