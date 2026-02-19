---
title: "ML Experiments"
description: "Reproducibility, resource-awareness, and lightweight MLOps."
summary: "Practical guidance for reproducible, resource-aware ML experiments with lightweight MLOps and deterministic evaluation."
tags: ["ml"]
categories: ["principles"]
draft: false
---

## Reproducibility

Pin all dependencies (including minor versions), record random seeds, dataset versions, and hardware configs, and use Docker for consistent environments. A non-reproducible result is just noise.

Create a `requirements.lock` (or `poetry.lock`, `uv.lock`) that captures exact versions. In your training script, log: Python version, CUDA version, GPU model, random seeds for Python/NumPy/PyTorch, dataset commit hash or version tag, and all hyperparameters. Store this metadata alongside the model checkpoint. When someone says "I can't reproduce your results," you should be able to hand them a single config file that recreates the exact environment.

See how [AI/ML Workshop]({{< ref "/deep-dives/ai-ml-workshop" >}}) approaches reproducibility with environment management and dependency pinning for ML examples.

**Anti-pattern — "Works on My Machine" ML:** Training a model without recording the environment or seed, then being unable to reproduce the result. Worse: publishing results you can't reproduce. Every ML paper retraction and every "model stopped working after re-training" incident traces back to reproducibility gaps. Pin everything.

## Resource-aware Design

Provide CPU/GPU fallbacks and design examples to run on modest hardware with smaller models or techniques like LoRA. Accessibility determines community engagement; gate-keeping on expensive hardware kills adoption.

Structure your code with a resource-aware configuration: `device: auto | cpu | cuda | mps`, `model_size: small | medium | large`, `precision: fp32 | fp16 | int8`. Auto-detect available hardware and select appropriate defaults. For GPU-heavy training, support gradient checkpointing and mixed precision to reduce VRAM requirements. Provide a "lite" mode that runs on a laptop's CPU in reasonable time.

**Anti-pattern — "Requires 8x A100" Examples:** Publishing ML examples that only work on enterprise-grade hardware. Most learners and contributors have a laptop with maybe one GPU. If your example requires $50k of hardware to even start, you've excluded 99% of your potential community. Provide scaled-down configurations that run in minutes on a CPU.

## Deterministic Evaluation

Use fixed train/test/validation splits with reproducible shuffling and implement deterministic metrics. Variability in results makes it hard to know what actual changes you're measuring.

Lock your data splits by either saving split indices explicitly or using a deterministic hash-based split (`hash(id) % 10 < 8` for 80/20 train/test). Set `torch.use_deterministic_algorithms(True)` in PyTorch or equivalent settings in your framework. When comparing experiments, statistical significance testing (paired t-tests, bootstrap confidence intervals) tells you whether a 0.3% accuracy improvement is real or noise.

**Anti-pattern — Random Split, Random Seed:** Re-splitting data and re-seeding randomness for each experiment run. You observe a 2% improvement but can't tell if it's from your code change or from a lucky split. Comparing experiments requires controlled variables—the data split and seed should be among the most tightly controlled.

## Artifact Management

Version model checkpoints, tokenizers, and datasets with checksums for integrity and use structured naming conventions for easy retrieval. Artifact management is unglamorous but critical for replayability.

Use a naming convention like `{model_name}/{version}/{timestamp}/` and store a `metadata.json` alongside each checkpoint containing training config, metrics, dataset version, and parent checkpoint (if fine-tuned). Tools like MLflow, W&B, or even a simple S3 bucket with consistent naming provide the backbone. The key requirement: given any deployed model, you can trace back to the exact training data, code, and config that produced it.

**Anti-pattern — "model_final_v2_FINAL_use_this_one.pt":** Saving checkpoints with ad-hoc names and no metadata. Within a week you can't remember which one is which, what hyperparameters produced it, or what dataset it was trained on. Structured naming with automated metadata capture prevents this.

## Profiling and Benchmarking

Measure wall-clock time, memory, and accelerator utilization rather than guessing where bottlenecks are. Automate common micro-benchmarks to catch regressions early.

Use `torch.profiler` or `nvidia-smi dmon` to identify whether you're GPU-bound (high utilization, training is compute-limited), data-bound (low utilization, data loading is the bottleneck), or memory-bound (frequent OOMs or swapping). Common fixes for data-bound training: increase `num_workers` in DataLoader, use memory-mapped datasets, or pre-tokenize/pre-process offline.

See the [Algorithms & Performance]({{< ref "/principles/algorithms-performance" >}}) principles for general profiling-driven optimization guidance that applies to ML workloads.

**Anti-pattern — Blind Batch Size Tuning:** Increasing batch size to "speed up training" without profiling. If you're data-bound, a larger batch size just increases the wait time per step. If you're memory-bound, you OOM. Profile first, then adjust the right knob.

## Lightweight MLOps

Start with simple reproducible scripts before adding complex pipelines—YAGNI applies to infrastructure. Automate smoke tests in CI and use tools like MLflow for lightweight tracking without enterprise overhead.

The progression should be: (1) a single training script with argparse and JSON config, (2) add MLflow/W&B tracking when you have more than 5 experiments to compare, (3) add automated evaluation in CI when you have regression test datasets, (4) add pipeline orchestration (Airflow, Prefect) only when you have recurring training jobs. Most teams jump to step 4 on day one and drown in infrastructure complexity.

**Anti-pattern — Kubernetes on Day One:** Deploying Kubeflow, Airflow, and a feature store before you have a working training script. Infrastructure complexity should follow experiment complexity, not precede it. If you're running 3 experiments a month from a Jupyter notebook, you don't need a pipeline orchestrator—you need a well-organized script with config files.

See the [Model Serving]({{< ref "/designs/model-serving" >}}) design for when you do need production-grade ML infrastructure: model versioning, canary deployment, and A/B testing at scale.

## Privacy & Data Handling

Avoid including sensitive or personal data in examples and provide synthetic or public datasets. Examples are code too; treat privacy seriously from the start.

Use established public datasets (ImageNet, COCO, WikiText) or generate synthetic data for examples and tutorials. If your project involves personal data (medical images, user text), provide clear documentation on data handling: where it's stored, who has access, how long it's retained, and how to delete it. Include a `data_card.md` that documents dataset provenance, demographics, and known biases.

See the [Privacy & Agents]({{< ref "/principles/privacy-agents" >}}) principles for comprehensive guidance on data minimization, consent, and audit logging.

**Anti-pattern — PII in Training Data:** Including personally identifiable information (names, emails, addresses, faces) in training datasets without anonymization. Models can memorize and regurgitate PII, creating legal liability and ethical violations. Anonymize, aggregate, or use synthetic data for development.

## Education-first Examples

Keep code minimal and well-commented, structure examples to be expandable, and explain design tradeoffs. Good examples are investments that multiply through the community.

Each example should have: (1) a README explaining what it demonstrates and what to expect, (2) a single-command run instruction (`python train.py --config examples/config.yaml`), (3) expected output or metrics so the user knows it worked, and (4) "next steps" pointing to more advanced configurations. Optimize for the reader's first 15 minutes—if they can't get a result in that time, they'll abandon the project.

## Foundational Theory & Practice

Build strong foundations in supervised/unsupervised learning, neural networks, and optimization. Understanding math underpinnings means informed implementation choices instead of cargo-cult coding.

Study the fundamentals: gradient descent mechanics, loss function design, regularization theory, bias-variance tradeoff, attention mechanisms. When you understand *why* learning rate warmup helps transformers or *why* batch normalization stabilizes training, you can debug training failures from first principles rather than blindly trying Stack Overflow suggestions.

**Anti-pattern — Copy-Paste ML:** Copying training loops from tutorials without understanding the components. When training diverges, you have no mental model for diagnosis—is it the learning rate, the loss function, the data, or a bug? Foundational understanding turns "it doesn't work" into "the loss is NaN because gradients exploded due to an unscaled learning rate with this optimizer."
