"""Select on validation using the declared quality and memory gates, then check predictions."""

QUALITY_PATH = {"qkv-fp32": "ffn_int8", "qkv-int8": "dual_int8", "qkv-npu": "dual_int8"}


def rank_candidates(prompts, quality, manifests, memory, gates, budget):
    rows = []
    for mode, label in QUALITY_PATH.items():
        for i, request in enumerate(prompts[0]["modes"][mode]["valid"]):
            width = request["width"]
            metrics = quality[str(width)]
            quant, fp = metrics[label], metrics["fp32"]
            good = (quant["exact"] >= gates["min_exact_of_64"]
                    and quant["exact"] >= fp["exact"] - gates["max_exact_loss_vs_fp32"]
                    and quant["conditional_ppl"] <= fp["conditional_ppl"] * gates["max_conditional_ppl_ratio_vs_fp32"]
                    and quant["conditional_ppl"] < metrics["bigram"]["conditional_ppl"])
            fits = (manifests[str(width)]["package_bytes"] <= budget["one_model_package_bytes"]
                    and memory["linked_writable_bytes"] <= budget["linked_writable_bytes_including_stack"]
                    and memory["array_local_bytes"] <= budget["array_local_bytes"])
            cycles = [prompt["modes"][mode]["valid"][i]["request_cycles"] for prompt in prompts]
            rows.append(dict(width=width, mode=mode, quality_pass=good, memory_pass=fits,
                             mean_request_cycles=sum(cycles)/len(cycles), eligible=good and fits))
    return sorted(rows, key=lambda row: (not row["eligible"], row["mean_request_cycles"]))


def compare_stages(prompts):
    comparisons = []
    for prompt in prompts:
        modes = prompt["modes"]
        for fp, npu in zip(modes["qkv-fp32"]["valid"], modes["qkv-npu"]["valid"]):
            lead, *decode = fp["stage_cycles"]
            fp_steps, npu_steps = fp["step_cycles"], npu["step_cycles"]
            prefill_saving = 1 - npu_steps[0]/fp_steps[0]
            decode_saving = 1 - sum(npu_steps[1:])/sum(fp_steps[1:])
            comparisons.append(dict(
                prompt=prompt["prompt"], width=fp["width"],
                prefill_qkv_exceeds_head=lead["input_norm_qkv"] > lead["vocabulary_head"],
                each_decode_head_exceeds_qkv=all(s["vocabulary_head"] > s["input_norm_qkv"] for s in decode),
                prefill_compute_saved_fraction=prefill_saving, decode_compute_saved_fraction=decode_saving,
                greater_relative_saving_at_prefill=prefill_saving > decode_saving,
            ))
    return comparisons
