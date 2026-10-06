import json
import zipfile
from pathlib import Path

import requests
import pyzipper


REPO_URL = "https://github.com/netop-team/TeleQnA.git"

ZIP_URL = (
    "https://raw.githubusercontent.com/netop-team/TeleQnA/main/TeleQnA.zip"
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

ZIP_PATH = DATA_DIR / "TeleQnA.zip"
FULL_DATASET_PATH = DATA_DIR / "TeleQnA.json"

EVAL_OUTPUT = BASE_DIR / "TeleQnA_3GPP_eval.json"
GOLD_OUTPUT = BASE_DIR / "gold_answers.json"

PASSWORD = b"teleqnadataset"

CATEGORY = "Standards specifications"
QUESTION_FILTER = "3GPP"


# ============================================================
# CREATE DATA DIRECTORY
# ============================================================

DATA_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DOWNLOAD TELEQNA ZIP
# ============================================================

def download_dataset():
    if ZIP_PATH.exists():
        print("[INFO] Dataset already exists:")
        print(f"       {ZIP_PATH}")
        return

    print("[INFO] Downloading TeleQnA dataset...")

    response = requests.get(
        ZIP_URL,
        stream=True,
        timeout=120,
    )
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(ZIP_PATH, "wb") as f:
        for chunk in response.iter_content(
            chunk_size=1024 * 1024
        ):
            if not chunk:
                continue

            f.write(chunk)
            downloaded += len(chunk)

            if total_size:
                percent = downloaded * 100 / total_size
                print(
                    f"\r       Downloaded: {percent:.1f}%",
                    end="",
                )

    print()
    print("[INFO] Download complete.")


# ============================================================
# EXTRACT TELEQNA JSON
# ============================================================

def extract_dataset():
    if FULL_DATASET_PATH.exists():
        print("[INFO] TeleQnA.json already extracted.")
        return

    print("[INFO] Extracting TeleQnA.json...")

    with pyzipper.AESZipFile(ZIP_PATH) as z:
        z.setpassword(PASSWORD)

        names = z.namelist()

        # The official archive contains TeleQnA.txt.
        # Some versions may contain TeleQnA.json instead.
        target = None

        for name in names:
            if name.lower().endswith("teleqna.txt"):
                target = name
                break

            if name.lower().endswith("teleqna.json"):
                target = name
                break

        if target is None:
            raise FileNotFoundError(
                "Could not find TeleQnA.txt or TeleQnA.json "
                "inside the archive."
            )

        raw_data = z.read(target)

        # Save raw extracted file temporarily
        temp_path = DATA_DIR / "TeleQnA_raw.txt"

        with open(temp_path, "wb") as f:
            f.write(raw_data)

        print(f"[INFO] Extracted: {target}")


# ============================================================
# LOAD JSON DATA
# ============================================================

def load_dataset():
    # --------------------------------------------------------
    # First try TeleQnA.json
    # --------------------------------------------------------

    if FULL_DATASET_PATH.exists():
        print("[INFO] Loading TeleQnA.json...")

        with open(
            FULL_DATASET_PATH,
            "r",
            encoding="utf-8",
        ) as f:
            return json.load(f)

    # --------------------------------------------------------
    # Otherwise parse extracted TeleQnA.txt
    # --------------------------------------------------------

    raw_path = DATA_DIR / "TeleQnA_raw.txt"

    if not raw_path.exists():
        raise FileNotFoundError(
            "Extracted TeleQnA file was not found."
        )

    print("[INFO] Parsing extracted TeleQnA.txt...")

    with open(
        raw_path,
        "r",
        encoding="utf-8",
    ) as f:
        text = f.read()

    # Try normal JSON first
    try:
        data = json.loads(text)

    except json.JSONDecodeError:
        # Some TeleQnA distributions use a Python/JSON-like
        # dictionary format. Try line-based JSON records.
        data = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not data:
            raise ValueError(
                "Unable to parse TeleQnA dataset."
            )

    # Save normalized full dataset
    with open(
        FULL_DATASET_PATH,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
        )

    return data


# ============================================================
# NORMALIZE DATASET
# ============================================================

def normalize_records(data):
    """
    TeleQnA may be represented either as:

        [
            {...},
            {...}
        ]

    or as:

        {
            "question 1": {...},
            "question 2": {...}
        }
    """

    if isinstance(data, dict):
        # If the dictionary itself represents one question
        if "question" in data:
            return [data]

        # Otherwise question IDs are keys
        records = []

        for key, value in data.items():
            if isinstance(value, dict):
                record = value.copy()

                record.setdefault(
                    "question_id",
                    key,
                )

                records.append(record)

        return records

    if isinstance(data, list):
        return data

    raise TypeError(
        f"Unsupported TeleQnA format: {type(data)}"
    )


# ============================================================
# FILTER 3GPP QUESTIONS
# ============================================================

def filter_3gpp(records):
    filtered = []

    for index, item in enumerate(records):
        category = str(
            item.get("category", "")
        ).strip()

        question = str(
            item.get("question", "")
        ).strip()

        # Exact benchmark filtering:
        #
        # category == Standards specifications
        #
        # AND
        #
        # question contains "3GPP"

        if (
            category == CATEGORY
            and QUESTION_FILTER.lower() in question.lower()
        ):
            record = item.copy()

            # Add a stable local ID
            record.setdefault(
                "question_id",
                f"3gpp_{len(filtered) + 1:04d}",
            )

            filtered.append(record)

    return filtered


# ============================================================
# CREATE EVALUATION DATASET
# ============================================================

def create_evaluation_dataset(records):
    evaluation = []

    for item in records:
        eval_item = {
            "question_id": item["question_id"],
            "question": item["question"],
            "option 1": item.get("option 1", ""),
            "option 2": item.get("option 2", ""),
            "option 3": item.get("option 3", ""),
            "option 4": item.get("option 4", ""),
            "category": item.get("category", ""),
        }

        evaluation.append(eval_item)

    return evaluation


# ============================================================
# CREATE GOLD ANSWERS
# ============================================================

def create_gold_answers(records):
    gold = []

    for item in records:
        gold_item = {
            "question_id": item["question_id"],
            "answer": item.get("answer", ""),
            "explanation": item.get("explanation", ""),
            "category": item.get("category", ""),
        }

        gold.append(gold_item)

    return gold


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("TeleQnA → 3GPP Evaluation Dataset")
    print("=" * 70)

    # 1. Download
    download_dataset()

    # 2. Extract
    extract_dataset()

    # 3. Load
    data = load_dataset()

    # 4. Normalize
    records = normalize_records(data)

    print()
    print(f"[INFO] Total TeleQnA records: {len(records)}")

    # 5. Filter
    threegpp_records = filter_3gpp(records)

    print(
        f"[INFO] 3GPP evaluation records: "
        f"{len(threegpp_records)}"
    )

    # --------------------------------------------------------
    # Sanity check
    # --------------------------------------------------------

    if len(threegpp_records) == 0:
        raise RuntimeError(
            "No 3GPP questions were found. "
            "Check the TeleQnA format and category names."
        )

    # --------------------------------------------------------
    # Create evaluation dataset
    # --------------------------------------------------------

    evaluation = create_evaluation_dataset(
        threegpp_records
    )

    # --------------------------------------------------------
    # Create gold answers
    # --------------------------------------------------------

    gold = create_gold_answers(
        threegpp_records
    )

    # --------------------------------------------------------
    # Save evaluation dataset
    # --------------------------------------------------------

    with open(
        EVAL_OUTPUT,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            evaluation,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Save gold answers
    # --------------------------------------------------------

    with open(
        GOLD_OUTPUT,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            gold,
            f,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("DONE")
    print("=" * 70)
    print()

    print(
        f"Total TeleQnA questions : {len(records)}"
    )

    print(
        f"3GPP questions         : "
        f"{len(threegpp_records)}"
    )

    print()
    print("Created files:")
    print(f"  {EVAL_OUTPUT}")
    print(f"  {GOLD_OUTPUT}")

    print()
    print("Evaluation dataset contains:")
    print("  - question_id")
    print("  - question")
    print("  - option 1")
    print("  - option 2")
    print("  - option 3")
    print("  - option 4")
    print("  - category")

    print()
    print("Gold dataset contains:")
    print("  - question_id")
    print("  - answer")
    print("  - explanation")
    print("  - category")

    print()
    print("The answer and explanation are NOT included")
    print("in TeleQnA_3GPP_eval.json.")


if __name__ == "__main__":
    main()
