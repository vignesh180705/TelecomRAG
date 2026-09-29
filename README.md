# TelecomRAG

```
import torch
import time

max_new_tokens = 1024

# Warmup
with torch.inference_mode():
    _ = model.generate(
        **inputs,
        max_new_tokens=10,
        do_sample=False,
        use_cache=True,
        pad_token_id=tokenizer.eos_token_id,
    )

torch.cuda.synchronize()

start = torch.cuda.Event(enable_timing=True)
end = torch.cuda.Event(enable_timing=True)

start.record()

with torch.inference_mode():
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        use_cache=True,
        pad_token_id=tokenizer.eos_token_id,
    )

end.record()

torch.cuda.synchronize()

elapsed = start.elapsed_time(end) / 1000

generated_tokens = outputs.shape[1] - inputs["input_ids"].shape[1]

print(f"Generated tokens: {generated_tokens}")
print(f"Time: {elapsed:.2f}s")
print(f"Speed: {generated_tokens / elapsed:.2f} tok/s")

```
