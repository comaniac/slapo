"""The tuning configuration for Bert. Example usage (assuming you are under 'benchmark'):
python3 -m ms.tune --config ../examples/bert/tune_cfg.py \
    --db bert-gpu8-seq512.json --error-stop symbol \
    bench.py hf ../examples/bert/pretrain_hf_bert.py --model bert-large-uncased --gpus 8 \
        --seq-len 512 --batch-size batch_size --gradient-checkpoint ckpt_ratio
"""
import re

def update_space(args, space):
    # Fix GPU number
    n_gpu = int(args["gpus"])

    # Batch size. When it is large (>100), also consider an alternative one.
    batch_size = space.create_symbol("batch_size", [16 * n_gpu])
    if 16 * n_gpu > 100:
        batch_size.add(12 * n_gpu)

    ckpt_ratio_cand = [1.0]
    if batch_size >= 96:
        ckpt_ratio_cand += [0.92, 0.84, 0.67]
    ckpt_ratio_cand += [0.5, 0.34, 0.25]

    space.create_symbol("ckpt_ratio", ckpt_ratio_cand)
    return space


def parse_log(unused):
    with open("log.txt") as f:
        text = f.read()

    def query(key):
        values = re.findall(key + ": +([\d\.]+)", text)
        if not values:
            return None
        return [float(v) for v in values]

    if "CUDA out of memory" in text:
        return (1, 0, text)

    batch_size = query("global batch size")
    if not batch_size:
        return (2, 0, text)   
    batch_size = int(batch_size[0])

    iter_times = query("elapsed time per iteration \(ms\)")
    if not iter_times:
        return (2, 0, text)

    # 1. Every 5 steps, Megatron reports the average iteration time of the past 5 steps.
    # 2. We remove the first value (of the first 5 steps) as the warmup.
    steps = 5 * (len(iter_times) - 1)
    avg_time = sum(iter_times[1:] * 5) / steps
    return (0, batch_size / avg_time * 1e3, text)