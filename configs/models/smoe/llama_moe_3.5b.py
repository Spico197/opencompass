from opencompass.models import LlamaMoECausalLM


models = [
    # LLaMA 13B
    dict(
        type=LlamaMoECausalLM,
        abbr='llama-moe-3.5b',
        # path="/mnt/petrelfs/share_data/quxiaoye/runs/llama2_random_scale4_112gpus_dynamic_data/outputs/cpt-llama2_random_scale4_112gpus_dynamic_data-2356022/checkpoint-13600/",
        # tokenizer_path='/mnt/petrelfs/share_data/quxiaoye/runs/llama2_random_scale4_112gpus_dynamic_data/outputs/cpt-llama2_random_scale4_112gpus_dynamic_data-2356022/checkpoint-13600/',
        path="/mnt/petrelfs/share_data/quxiaoye/runs/llama2_random_split_112gpus_8_2/outputs/cpt-llama2_random_split_112gpus_8_2-2377343/checkpoint-13600/",
        tokenizer_path='/mnt/petrelfs/share_data/quxiaoye/runs/llama2_random_split_112gpus_8_2/outputs/cpt-llama2_random_split_112gpus_8_2-2377343/checkpoint-13600/',
        tokenizer_kwargs=dict(padding_side='left',
                              truncation_side='left',
                              use_fast=False,
                              ),
        max_out_len=100,
        max_seq_len=2048,
        batch_size=8,
        model_kwargs=dict(device_map='auto'),
        batch_padding=False, # if false, inference with for-loop without batch padding
        run_cfg=dict(num_gpus=1, num_procs=1),
    )
]
