from datasets import load_dataset

ds = load_dataset("DinoStackAI/3GPP-QA-MultipleChoice")

ds.save_to_disk("./3GPP-QA-MultipleChoice")
